import json

from django import forms as django_forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from billing.models import Invoice, Payment
from billing.services import record_payment
from core.forms import SmartSelectMixin
from patients.models import Patient


class PaymentForm(SmartSelectMixin, django_forms.Form):
    amount = django_forms.DecimalField(max_digits=12, decimal_places=2,
                                       widget=django_forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}))
    mode = django_forms.ChoiceField(choices=Payment.Mode.choices,
                                    widget=django_forms.Select(attrs={"class": "form-select"}))
    reference = django_forms.CharField(required=False, widget=django_forms.TextInput(attrs={"class": "form-control"}))
    notes = django_forms.CharField(required=False, widget=django_forms.Textarea(attrs={"rows": 2, "class": "form-control"}))


@method_decorator(login_required, name="dispatch")
class BillingListView(View):
    template_name = "billing/list.html"

    def get(self, request):
        from django.core.paginator import Paginator
        from django.db.models import Count, Sum
        from django.utils import timezone

        patient_pk = request.GET.get("patient")
        status_filter = request.GET.get("status", "")

        # Base scope: all invoices, narrowed to a patient when viewing their bills.
        # The status dropdown only narrows the invoice *table*, not the headline
        # figures — a dashboard should always show the whole financial picture.
        base_qs = Invoice.objects.select_related("patient", "encounter").order_by("-created_at")
        patient = None
        if patient_pk:
            patient = get_object_or_404(Patient, pk=patient_pk)
            base_qs = base_qs.filter(patient=patient)

        # ── Headline figures (exclude void invoices from money totals) ──
        financial_qs = base_qs.exclude(status=Invoice.Status.VOID)
        agg = financial_qs.aggregate(
            total_billed=Sum("total"),
            total_paid=Sum("amount_paid"),
            total_balance=Sum("balance"),
        )
        total_billed = agg["total_billed"] or 0
        total_paid = agg["total_paid"] or 0
        total_balance = agg["total_balance"] or 0
        collection_rate = round((total_paid / total_billed) * 100, 1) if total_billed else 0

        # ── Invoice status breakdown (counts + billed amount per status) ──
        status_labels = dict(Invoice.Status.choices)
        status_rows = []
        for row in (
            base_qs.values("status")
            .annotate(n=Count("id"), amt=Sum("total"))
            .order_by("-amt")
        ):
            status_rows.append({
                "status": row["status"],
                "label": status_labels.get(row["status"], row["status"]),
                "count": row["n"],
                "amount": row["amt"] or 0,
            })

        # ── Payment analytics (real cash received) ──
        today = timezone.localdate()
        month_start = today.replace(day=1)
        payments = Payment.objects.filter(invoice__in=base_qs)
        collected_today = payments.filter(received_at__date=today).aggregate(s=Sum("amount"))["s"] or 0
        collected_month = payments.filter(received_at__date__gte=month_start).aggregate(s=Sum("amount"))["s"] or 0
        mode_labels = dict(Payment.Mode.choices)
        mode_rows = [
            {
                "mode": r["mode"],
                "label": mode_labels.get(r["mode"], r["mode"]),
                "amount": r["s"] or 0,
                "count": r["n"],
            }
            for r in payments.values("mode").annotate(s=Sum("amount"), n=Count("id")).order_by("-s")
        ]

        # ── Invoice table (status filter applies here only) ──
        list_qs = base_qs
        if status_filter:
            list_qs = list_qs.filter(status=status_filter)
        paginator = Paginator(list_qs, 30)
        page = paginator.get_page(request.GET.get("page", 1))

        return render(request, self.template_name, {
            "invoices": page,
            "page_obj": page,
            "patient": patient,
            "status_filter": status_filter,
            "status_choices": Invoice.Status.choices,
            "total_count": list_qs.count(),
            # dashboard
            "total_billed": total_billed,
            "total_paid": total_paid,
            "total_balance": total_balance,
            "collection_rate": collection_rate,
            "status_rows": status_rows,
            "collected_today": collected_today,
            "collected_month": collected_month,
            "mode_rows": mode_rows,
            "invoice_count": financial_qs.count(),
        })


@method_decorator(login_required, name="dispatch")
class InvoiceDetailView(View):
    template_name = "billing/invoice.html"

    def get(self, request, pk):
        from billing.models import PaystackTransaction
        invoice = get_object_or_404(Invoice, pk=pk)
        paystack_txs = PaystackTransaction.objects.filter(invoice=invoice).order_by("-created_at")[:5]
        return render(request, self.template_name, {
            "invoice": invoice,
            "patient": invoice.patient,
            "form": PaymentForm(initial={"amount": invoice.balance}),
            "paystack_transactions": paystack_txs,
        })


@method_decorator(login_required, name="dispatch")
class PaymentCreateView(View):
    def post(self, request, invoice_pk):
        invoice = get_object_or_404(Invoice, pk=invoice_pk)
        form = PaymentForm(request.POST)
        if form.is_valid():
            record_payment(
                invoice,
                amount=form.cleaned_data["amount"],
                mode=form.cleaned_data["mode"],
                reference=form.cleaned_data.get("reference", ""),
                cashier=request.user,
                notes=form.cleaned_data.get("notes", ""),
            )
            messages.success(request, f"Payment of ₦{form.cleaned_data['amount']} recorded.")
            return redirect("billing:invoice", pk=invoice_pk)
        return render(request, "billing/invoice.html", {
            "invoice": invoice, "patient": invoice.patient, "form": form
        })


@method_decorator(login_required, name="dispatch")
class InvoicePDFView(View):
    def get(self, request, pk):
        invoice = get_object_or_404(
            Invoice.objects.select_related("patient", "encounter")
            .prefetch_related("items__service", "payments"),
            pk=pk,
        )

        pdf_bytes = self._render_html_pdf(request, invoice)
        if pdf_bytes is None:
            # WeasyPrint unavailable on this host — fall back to the ReportLab build.
            from core.pdf_utils import build_invoice_pdf
            pdf_bytes = build_invoice_pdf(invoice).read()

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="invoice-{invoice.invoice_number}.pdf"'
        )
        return response

    def _render_html_pdf(self, request, invoice):
        """Render the same HTML used on the invoice page into a PDF via WeasyPrint.

        Returns the PDF bytes, or None if WeasyPrint isn't installed/working
        (e.g. missing native libs on the host), so the caller can fall back.
        """
        try:
            from weasyprint import HTML
        except Exception:
            return None
        from django.template.loader import render_to_string

        html = render_to_string("billing/invoice_pdf.html", {"invoice": invoice}, request=request)
        try:
            return HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
        except Exception:
            return None


@method_decorator(login_required, name="dispatch")
class PaystackInitiateView(View):
    """POST from invoice detail → redirect to Paystack hosted checkout."""

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        if invoice.balance <= 0:
            messages.error(request, "Invoice is already fully paid.")
            return redirect("billing:invoice", pk=pk)

        from billing.paystack import initialize
        callback_url = request.build_absolute_uri(
            f"/billing/paystack/callback/?invoice={pk}"
        )
        try:
            tx = initialize(invoice, initiated_by=request.user, callback_url=callback_url)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("billing:invoice", pk=pk)

        return redirect(tx.authorization_url)


class PaystackCallbackView(View):
    """Paystack redirects here after checkout (success or cancel)."""

    def get(self, request):
        reference = request.GET.get("reference", "")
        invoice_pk = request.GET.get("invoice", "")

        if not reference:
            messages.error(request, "No payment reference received.")
            if invoice_pk:
                return redirect("billing:invoice", pk=invoice_pk)
            return redirect("billing:list")

        from billing.paystack import verify
        try:
            tx = verify(reference)
        except ValueError as e:
            messages.error(request, f"Payment verification failed: {e}")
            return redirect("billing:invoice", pk=tx.invoice_id if hasattr(tx, 'invoice_id') else invoice_pk)

        if tx.status == "success":
            messages.success(
                request,
                f"Payment of ₦{tx.amount_naira:,.2f} received. Thank you!"
            )
        else:
            messages.warning(request, f"Payment not completed ({tx.gateway_response or tx.status}).")

        return redirect("billing:invoice", pk=tx.invoice_id)


@csrf_exempt
def paystack_webhook(request):
    """
    Paystack webhook endpoint — no CSRF, signature-verified.
    Always returns 200 to stop Paystack retrying.
    """
    if request.method != "POST":
        return HttpResponse(status=405)

    signature = request.headers.get("X-Paystack-Signature", "")
    try:
        from billing.paystack import handle_webhook
        handle_webhook(request.body, signature)
    except ValueError:
        return HttpResponse(status=400)
    except Exception:
        pass  # Log in production; don't expose internals to Paystack

    return HttpResponse(status=200)
