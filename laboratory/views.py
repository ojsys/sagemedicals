from django import forms as django_forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from core.forms import SmartSelectMixin
from encounters.models import Encounter
from laboratory.models import LabOrder, LabResult, LabTest


class LabOrderForm(SmartSelectMixin, django_forms.ModelForm):
    class Meta:
        model = LabOrder
        fields = ["test", "priority", "clinical_notes"]
        widgets = {"clinical_notes": django_forms.Textarea(attrs={"rows": 2, "class": "form-control"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["test"].queryset = LabTest.objects.filter(is_active=True)
        self.fields["test"].widget.attrs["class"] = "form-select"
        self.fields["priority"].widget.attrs["class"] = "form-select"


class LabTestForm(SmartSelectMixin, django_forms.ModelForm):
    class Meta:
        model = LabTest
        fields = [
            "code", "name", "panel", "sample_type",
            "turnaround_hours", "price", "units", "reference_range_note",
        ]
        widgets = {
            "code": django_forms.TextInput(attrs={"placeholder": "e.g. MP, FBC, RFT"}),
            "name": django_forms.TextInput(attrs={"placeholder": "e.g. Malaria Parasite Test"}),
            "panel": django_forms.TextInput(attrs={
                "placeholder": "e.g. Microbiology, Haematology",
                "list": "lab-panel-options",
            }),
            "units": django_forms.TextInput(attrs={"placeholder": "e.g. mg/dL"}),
            "reference_range_note": django_forms.TextInput(attrs={"placeholder": "e.g. 70-110 (fasting)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, f in self.fields.items():
            if isinstance(f.widget, django_forms.Select):
                f.widget.attrs.setdefault("class", "form-select")
            else:
                f.widget.attrs.setdefault("class", "form-control")
        self.fields["code"].required = True
        self.fields["name"].required = True

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()


class LabResultForm(SmartSelectMixin, django_forms.ModelForm):
    class Meta:
        model = LabResult
        fields = ["value", "unit", "reference_low", "reference_high", "abnormal_flag", "is_critical", "notes"]
        widgets = {"notes": django_forms.Textarea(attrs={"rows": 2, "class": "form-control"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, f in self.fields.items():
            if isinstance(f.widget, django_forms.Select):
                f.widget.attrs["class"] = "form-select"
            elif not isinstance(f.widget, (django_forms.CheckboxInput, django_forms.Textarea)):
                f.widget.attrs["class"] = "form-control"


@method_decorator(login_required, name="dispatch")
class LabOrderCreateView(View):
    def post(self, request, encounter_pk):
        encounter = get_object_or_404(Encounter, pk=encounter_pk)
        form = LabOrderForm(request.POST)
        if form.is_valid():
            import random
            import string
            order = form.save(commit=False)
            order.patient = encounter.patient
            order.encounter = encounter
            order.ordering_clinician = request.user
            order.barcode = "LB" + "".join(random.choices(string.digits, k=8))
            order._current_user = request.user
            order.save()
            # Add to invoice
            from billing.services import add_invoice_item
            price = order.test.price
            add_invoice_item(encounter, f"Lab: {order.test.name}", price)

        if request.headers.get("HX-Request"):
            orders = encounter.lab_orders.all().select_related("test")
            return render(request, "laboratory/partials/lab_order_list.html",
                          {"lab_orders": orders, "encounter": encounter})
        return redirect("encounters:workspace", pk=encounter_pk)


@method_decorator(login_required, name="dispatch")
class LabWorklistView(View):
    template_name = "laboratory/worklist.html"

    def get(self, request):
        panel_filter = request.GET.get("panel", "")
        priority_filter = request.GET.get("priority", "")
        patient_pk = request.GET.get("patient")

        active_qs = LabOrder.objects.exclude(
            status__in=[LabOrder.Status.RELEASED, LabOrder.Status.CANCELLED]
        ).select_related("patient", "test", "ordering_clinician", "result")

        if patient_pk:
            active_qs = active_qs.filter(patient_id=patient_pk)
        if panel_filter:
            active_qs = active_qs.filter(test__panel=panel_filter)
        if priority_filter:
            active_qs = active_qs.filter(priority=priority_filter)

        # stat priority: STAT first, then urgent, then routine; within each by age
        priority_order = {"stat": 0, "urgent": 1, "routine": 2}
        orders = sorted(active_qs, key=lambda o: (priority_order.get(o.priority, 3), o.created_at))

        # Stats across ALL active (unfiltered for accuracy)
        all_active = LabOrder.objects.exclude(status__in=[LabOrder.Status.RELEASED, LabOrder.Status.CANCELLED])
        stats = {
            "pending_collection": all_active.filter(status=LabOrder.Status.ORDERED).count(),
            "in_progress": all_active.filter(status__in=[
                LabOrder.Status.SAMPLE_COLLECTED, LabOrder.Status.IN_PROGRESS
            ]).count(),
            "awaiting_verify": all_active.filter(status=LabOrder.Status.RESULTED).count(),
            "critical": all_active.filter(result__is_critical=True).exclude(
                result__critical_acknowledged_at__isnull=False
            ).count(),
        }

        panels = (
            LabTest.objects.filter(is_active=True)
            .values_list("panel", flat=True)
            .distinct()
            .order_by("panel")
        )

        return render(request, self.template_name, {
            "orders": orders,
            "stats": stats,
            "panels": panels,
            "panel_filter": panel_filter,
            "priority_filter": priority_filter,
        })


@method_decorator(login_required, name="dispatch")
class LabResultEntryView(View):
    template_name = "laboratory/result_entry.html"

    def get(self, request, pk):
        order = get_object_or_404(LabOrder, pk=pk)
        result = getattr(order, "result", None)
        return render(request, self.template_name, {
            "order": order,
            "form": LabResultForm(instance=result),
        })

    def post(self, request, pk):
        order = get_object_or_404(LabOrder, pk=pk)
        result = getattr(order, "result", None)
        form = LabResultForm(request.POST, instance=result)
        if form.is_valid():
            r = form.save(commit=False)
            r.order = order
            r.technician = request.user
            r._current_user = request.user
            r.save()
            order.status = LabOrder.Status.RESULTED
            order.save(update_fields=["status"])
            messages.success(request, "Result saved.")
            return redirect("laboratory:worklist")
        return render(request, self.template_name, {"order": order, "form": form})


@method_decorator(login_required, name="dispatch")
class LabResultVerifyView(View):
    def post(self, request, pk):
        order = get_object_or_404(LabOrder, pk=pk, status=LabOrder.Status.RESULTED)
        result = order.result
        result.verified_by = request.user
        result.verified_at = timezone.now()
        result.released_at = timezone.now()
        result._current_user = request.user
        result.save()
        order.status = LabOrder.Status.RELEASED
        order.save(update_fields=["status"])
        if result.is_critical:
            pass
        messages.success(request, "Result verified and released to clinician.")
        return redirect("laboratory:worklist")


@method_decorator(login_required, name="dispatch")
class SampleCollectView(View):
    def post(self, request, pk):
        order = get_object_or_404(LabOrder, pk=pk, status=LabOrder.Status.ORDERED)
        order.status = LabOrder.Status.SAMPLE_COLLECTED
        order.collected_at = timezone.now()
        order.collected_by = request.user
        order._current_user = request.user
        order.save(update_fields=["status", "collected_at", "collected_by"])
        messages.success(request, f"Sample collected for {order.test.name} — {order.patient.full_name}.")
        return redirect("laboratory:worklist")


@method_decorator(login_required, name="dispatch")
class CriticalAcknowledgeView(View):
    def post(self, request, pk):
        order = get_object_or_404(LabOrder, pk=pk)
        result = getattr(order, "result", None)
        if result and result.is_critical and not result.critical_acknowledged_at:
            result.critical_acknowledged_by = request.user
            result.critical_acknowledged_at = timezone.now()
            result._current_user = request.user
            result.save(update_fields=["critical_acknowledged_by", "critical_acknowledged_at"])
            messages.success(request, "Critical result acknowledged.")
        return redirect("laboratory:order_detail", pk=pk)


@method_decorator(login_required, name="dispatch")
class LabOrderDetailView(View):
    template_name = "laboratory/order_detail.html"

    def get(self, request, pk):
        order = get_object_or_404(
            LabOrder.objects.select_related(
                "patient", "test", "ordering_clinician",
                "collected_by", "result__technician", "result__verified_by",
                "result__critical_acknowledged_by"
            ),
            pk=pk,
        )
        result = getattr(order, "result", None)
        return render(request, self.template_name, {"order": order, "result": result})


@method_decorator(login_required, name="dispatch")
class LabResultPDFView(View):
    def get(self, request, pk):
        order = get_object_or_404(
            LabOrder.objects.select_related(
                "patient", "test",
                "result__entered_by", "result__verified_by",
            ),
            pk=pk, status__in=["verified", "released"],
        )
        from core.pdf_utils import build_lab_result_pdf
        buf = build_lab_result_pdf(order)
        fname = f"lab-{order.patient.hospital_number}-{order.test.name.lower().replace(' ', '-')}.pdf"
        response = HttpResponse(buf.read(), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{fname}"'
        return response


# ── Lab Test Catalogue ────────────────────────────────────────

@method_decorator(login_required, name="dispatch")
class LabTestCatalogueView(View):
    """List existing lab tests and add new ones inline."""

    template_name = "laboratory/test_catalogue.html"

    def get(self, request, form=None):
        qs = LabTest.objects.all().order_by("panel", "name")
        q = request.GET.get("q", "").strip()
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(name__icontains=q) | Q(code__icontains=q) | Q(panel__icontains=q)
            )
        panels = (
            LabTest.objects.exclude(panel="")
            .values_list("panel", flat=True).distinct().order_by("panel")
        )
        return render(request, self.template_name, {
            "tests": qs,
            "form": form or LabTestForm(),
            "q": q,
            "panels": panels,
            "total": LabTest.objects.count(),
            "active_count": LabTest.objects.filter(is_active=True).count(),
        })

    def post(self, request):
        form = LabTestForm(request.POST)
        if form.is_valid():
            test = form.save(commit=False)
            test._current_user = request.user
            test.save()
            messages.success(request, f"Test '{test.name}' added.")
            return redirect("laboratory:test_catalogue")
        return self.get(request, form=form)


@method_decorator(login_required, name="dispatch")
class LabTestEditView(View):
    template_name = "laboratory/test_edit.html"

    def get(self, request, pk):
        test = get_object_or_404(LabTest, pk=pk)
        return render(request, self.template_name, {"form": LabTestForm(instance=test), "test": test})

    def post(self, request, pk):
        test = get_object_or_404(LabTest, pk=pk)
        form = LabTestForm(request.POST, instance=test)
        if form.is_valid():
            updated = form.save(commit=False)
            updated._current_user = request.user
            updated.save()
            messages.success(request, f"Test '{updated.name}' updated.")
            return redirect("laboratory:test_catalogue")
        return render(request, self.template_name, {"form": form, "test": test})


@method_decorator(login_required, name="dispatch")
class LabTestToggleView(View):
    def post(self, request, pk):
        test = get_object_or_404(LabTest, pk=pk)
        test.is_active = not test.is_active
        test._current_user = request.user
        test.save(update_fields=["is_active"])
        state = "activated" if test.is_active else "deactivated"
        messages.success(request, f"Test '{test.name}' {state}.")
        return redirect("laboratory:test_catalogue")


def _remove_lab_invoice_item(order):
    """Best-effort: drop the matching InvoiceItem this lab order added (description-based match)."""
    if not order.encounter_id:
        return
    from billing.models import Invoice, InvoiceItem
    invoices = Invoice.objects.filter(encounter_id=order.encounter_id).exclude(status=Invoice.Status.PAID)
    for inv in invoices:
        item = InvoiceItem.objects.filter(
            invoice=inv, description=f"Lab: {order.test.name}"
        ).order_by("-created_at").first()
        if item:
            item.delete()
            inv.recalculate()
            return


@method_decorator(login_required, name="dispatch")
class LabOrderCancelView(View):
    """Cancel a lab order that hasn't been released yet and remove its billing line."""

    def post(self, request, pk):
        order = get_object_or_404(LabOrder, pk=pk)
        if order.status in (LabOrder.Status.RELEASED, LabOrder.Status.VERIFIED):
            messages.error(request, "Cannot cancel a released or verified order.")
            return redirect("laboratory:order_detail", pk=pk)
        order.status = LabOrder.Status.CANCELLED
        order._current_user = request.user
        order.save(update_fields=["status"])
        _remove_lab_invoice_item(order)
        messages.success(request, f"Lab order for {order.test.name} cancelled and billing line removed.")
        return redirect("laboratory:order_detail", pk=pk)


@method_decorator(login_required, name="dispatch")
class LabOrderDeleteView(View):
    """Hard-delete a cancelled lab order. Also removes any remaining billing line."""

    def post(self, request, pk):
        order = get_object_or_404(LabOrder, pk=pk)
        if order.status != LabOrder.Status.CANCELLED:
            messages.error(request, "Only cancelled orders can be deleted.")
            return redirect("laboratory:order_detail", pk=pk)
        # Belt and braces — remove any lingering billing item too.
        _remove_lab_invoice_item(order)
        label = order.test.name
        encounter_pk = order.encounter_id
        order.delete()
        messages.success(request, f"Cancelled lab order for {label} deleted.")
        if encounter_pk:
            return redirect("encounters:workspace", pk=encounter_pk)
        return redirect("laboratory:worklist")
