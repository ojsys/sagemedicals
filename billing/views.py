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
        from django.db.models import Sum

        patient_pk = request.GET.get("patient")
        status_filter = request.GET.get("status", "")

        qs = (
            Invoice.objects.select_related("patient", "encounter")
            .order_by("-created_at")
        )
        patient = None
        if patient_pk:
            patient = get_object_or_404(Patient, pk=patient_pk)
            qs = qs.filter(patient=patient)
        if status_filter:
            qs = qs.filter(status=status_filter)

        totals = qs.aggregate(
            total_billed=Sum("total"),
            total_paid=Sum("amount_paid"),
            total_balance=Sum("balance"),
        )

        paginator = Paginator(qs, 30)
        page = paginator.get_page(request.GET.get("page", 1))

        return render(request, self.template_name, {
            "invoices": page,
            "page_obj": page,
            "patient": patient,
            "status_filter": status_filter,
            "status_choices": Invoice.Status.choices,
            "totals": totals,
            "total_count": qs.count(),
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
            Invoice.objects.select_related("patient").prefetch_related("items__service"),
            pk=pk,
        )
        from core.pdf_utils import build_invoice_pdf
        buf = build_invoice_pdf(invoice)
        response = HttpResponse(buf.read(), content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="invoice-{invoice.invoice_number}.pdf"'
        )
        return response


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
