from datetime import timedelta

from django import forms as django_forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, Count, Q, When
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.defaultfilters import pluralize
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from core.forms import SmartSelectMixin
from encounters.models import Encounter
from laboratory.models import LabOrder, LabResult, LabTest
from laboratory.services import cancel_order, remove_lab_invoice_item
from patients.models import Patient


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


WORKLIST_PAGE_SIZE = 25

_S = LabOrder.Status
# Worklist tabs: key -> (label, statuses). "critical" is result-based and handled separately.
WORKLIST_TABS = {
    "active": ("Active", [_S.ORDERED, _S.SAMPLE_COLLECTED, _S.IN_PROGRESS, _S.RESULTED, _S.VERIFIED]),
    "pending": ("Pending Collection", [_S.ORDERED]),
    "in_progress": ("In Progress", [_S.SAMPLE_COLLECTED, _S.IN_PROGRESS]),
    "awaiting_verify": ("Awaiting Verify", [_S.RESULTED]),
    "critical": ("Critical", None),
    "released": ("Released", [_S.VERIFIED, _S.RELEASED]),
    "cancelled": ("Cancelled / Expired", [_S.CANCELLED, _S.REJECTED]),
    "all": ("All", None),
}
# Tabs that are queues to work through: urgent first, then oldest first.
QUEUE_TABS = {"active", "pending", "in_progress", "awaiting_verify", "critical"}
UNACKED_CRITICAL = Q(result__is_critical=True, result__critical_acknowledged_at__isnull=True)
PERIODS = {"today": 0, "7d": 7, "30d": 30}


def _safe_next(request, default="laboratory:worklist"):
    """Where to send the user after an action — back to their filtered worklist if given."""
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}, request.is_secure()):
        return next_url
    return reverse(default)


def _search_orders(qs, query):
    """Every word must match the patient's name/number, the barcode or the test."""
    for term in query.split():
        qs = qs.filter(
            Q(patient__first_name__icontains=term)
            | Q(patient__last_name__icontains=term)
            | Q(patient__hospital_number__icontains=term)
            | Q(barcode__icontains=term)
            | Q(test__name__icontains=term)
            | Q(test__code__icontains=term)
        )
    return qs


@method_decorator(login_required, name="dispatch")
class LabWorklistView(View):
    template_name = "laboratory/worklist.html"
    partial_template = "laboratory/partials/worklist_results.html"

    def get(self, request):
        from laboratory.services import LAB_ORDER_EXPIRY_HOURS, expire_stale_orders

        expire_stale_orders()

        query = request.GET.get("q", "").strip()
        panel_filter = request.GET.get("panel", "")
        priority_filter = request.GET.get("priority", "")
        period = request.GET.get("period", "")
        patient_pk = request.GET.get("patient")
        status = request.GET.get("status", "")
        if status not in WORKLIST_TABS:
            status = ""
        # Searching or viewing one patient means "find their requests" — look across every status.
        tab = status or ("all" if query or patient_pk else "active")

        qs = LabOrder.objects.select_related("patient", "test", "ordering_clinician", "result")
        patient = None
        if patient_pk:
            patient = get_object_or_404(Patient, pk=patient_pk)
            qs = qs.filter(patient=patient)
        if query:
            qs = _search_orders(qs, query)
        if panel_filter:
            qs = qs.filter(test__panel=panel_filter)
        if priority_filter:
            qs = qs.filter(priority=priority_filter)
        if period in PERIODS:
            since = timezone.localdate() - timedelta(days=PERIODS[period])
            qs = qs.filter(created_at__date__gte=since)

        # Tab counts reflect the current search/filters so it is obvious where matches live.
        counts = qs.aggregate(**{
            key: Count("pk", filter=UNACKED_CRITICAL if key == "critical" else Q(status__in=statuses))
            for key, (_, statuses) in WORKLIST_TABS.items() if key != "all"
        }, all=Count("pk"))
        tabs = [
            {"key": key, "label": label, "count": counts[key]}
            for key, (label, _) in WORKLIST_TABS.items()
        ]

        if tab == "critical":
            qs = qs.filter(UNACKED_CRITICAL)
        elif WORKLIST_TABS[tab][1]:
            qs = qs.filter(status__in=WORKLIST_TABS[tab][1])

        if tab in QUEUE_TABS:
            qs = qs.annotate(priority_rank=Case(
                When(priority=LabOrder.Priority.STAT, then=0),
                When(priority=LabOrder.Priority.URGENT, then=1),
                default=2,
            )).order_by("priority_rank", "created_at")
        else:
            qs = qs.order_by("-created_at")

        page = Paginator(qs, WORKLIST_PAGE_SIZE).get_page(request.GET.get("page", 1))

        now = timezone.now()
        for order in page:
            age_hours = (now - order.created_at).total_seconds() / 3600
            if order.status == LabOrder.Status.ORDERED:
                order.expires_in_hours = max(0, int(LAB_ORDER_EXPIRY_HOURS - age_hours))
            order.is_overdue = (
                order.status in (_S.SAMPLE_COLLECTED, _S.IN_PROGRESS, _S.RESULTED)
                and age_hours > order.test.turnaround_hours
            )

        ctx = {
            "page_obj": page,
            "orders": page.object_list,
            "tabs": tabs,
            "tab": tab,
            "tab_label": WORKLIST_TABS[tab][0],
            "status": status,
            "query": query,
            "patient": patient,
            "panel_filter": panel_filter,
            "priority_filter": priority_filter,
            "period": period,
            "expiry_hours": LAB_ORDER_EXPIRY_HOURS,
            "bulk_actionable": tab not in ("released", "cancelled"),
            "page_range": page.paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1),
            "return_url": request.get_full_path(),
            "today": timezone.localdate(),
            "is_htmx": bool(request.headers.get("HX-Request")),
        }
        if ctx["is_htmx"]:
            return render(request, self.partial_template, ctx)

        all_active = LabOrder.objects.filter(status__in=WORKLIST_TABS["active"][1])
        ctx["stats"] = {
            "pending_collection": all_active.filter(status=_S.ORDERED).count(),
            "in_progress": all_active.filter(status__in=WORKLIST_TABS["in_progress"][1]).count(),
            "awaiting_verify": all_active.filter(status=_S.RESULTED).count(),
            "critical": LabOrder.objects.filter(UNACKED_CRITICAL).count(),
        }
        ctx["panels"] = (
            LabTest.objects.exclude(panel="")
            .values_list("panel", flat=True)
            .distinct()
            .order_by("panel")
        )
        return render(request, self.template_name, ctx)


@method_decorator(login_required, name="dispatch")
class LabBulkActionView(View):
    """Collect samples for, or cancel, several selected worklist orders at once."""

    def post(self, request):
        action = request.POST.get("action")
        ids = [i for i in request.POST.getlist("orders") if i.isdigit()]
        next_url = _safe_next(request)

        if not ids:
            messages.error(request, "Select at least one order first.")
            return redirect(next_url)

        orders = LabOrder.objects.filter(pk__in=ids).select_related("test")
        if action == "collect":
            done = 0
            for order in orders.filter(status=_S.ORDERED):
                order.status = _S.SAMPLE_COLLECTED
                order.collected_at = timezone.now()
                order.collected_by = request.user
                order._current_user = request.user
                order.save(update_fields=["status", "collected_at", "collected_by"])
                done += 1
            skipped = len(ids) - done
            messages.success(request, f"Marked {done} sample{pluralize(done)} collected."
                             + (f" {skipped} skipped (not pending collection)." if skipped else ""))
        elif action == "cancel":
            reason = request.POST.get("reason", "").strip() or "Cancelled from worklist"
            done = 0
            for order in orders.exclude(status__in=[_S.RELEASED, _S.VERIFIED, _S.CANCELLED]):
                with transaction.atomic():
                    cancel_order(order, f"{reason} — {request.user.get_full_name() or request.user}", request.user)
                done += 1
            skipped = len(ids) - done
            messages.success(request, f"Cancelled {done} order{pluralize(done)} and removed unpaid billing lines."
                             + (f" {skipped} skipped (already released or cancelled)." if skipped else ""))
        else:
            messages.error(request, "Unknown bulk action.")
        return redirect(next_url)


@method_decorator(login_required, name="dispatch")
class LabResultEntryView(View):
    template_name = "laboratory/result_entry.html"

    def get(self, request, pk):
        order = get_object_or_404(LabOrder, pk=pk)
        result = getattr(order, "result", None)
        return render(request, self.template_name, {
            "order": order,
            "form": LabResultForm(instance=result),
            "next": _safe_next(request),
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
            return redirect(_safe_next(request))
        return render(request, self.template_name, {"order": order, "form": form, "next": _safe_next(request)})


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
        return redirect(_safe_next(request))


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
        return redirect(_safe_next(request))


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


@method_decorator(login_required, name="dispatch")
class LabOrderCancelView(View):
    """Cancel a lab order that hasn't been released yet and remove its billing line."""

    def post(self, request, pk):
        order = get_object_or_404(LabOrder, pk=pk)
        if order.status in (LabOrder.Status.RELEASED, LabOrder.Status.VERIFIED):
            messages.error(request, "Cannot cancel a released or verified order.")
            return redirect("laboratory:order_detail", pk=pk)
        reason = request.POST.get("reason", "").strip() or "Cancelled"
        cancel_order(order, f"{reason} — {request.user.get_full_name() or request.user}", request.user)
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
        remove_lab_invoice_item(order)
        label = order.test.name
        encounter_pk = order.encounter_id
        order.delete()
        messages.success(request, f"Cancelled lab order for {label} deleted.")
        if encounter_pk:
            return redirect("encounters:workspace", pk=encounter_pk)
        return redirect("laboratory:worklist")
