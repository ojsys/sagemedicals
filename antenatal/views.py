from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from django.db.models import Q

from patients.models import Patient

from .forms import ANCRecordForm, ANCVisitForm, ObstetricScanForm
from .models import ANCRecord, ANCVisit, ObstetricScan


# ── List ─────────────────────────────────────────────────────

@method_decorator(login_required, name="dispatch")
class ANCListView(View):
    template_name = "antenatal/list.html"

    def get(self, request):
        today = date.today()
        qs = (
            ANCRecord.objects.filter(is_active=True)
            .select_related("patient")
            .prefetch_related("visits")
            .order_by("edd")
        )

        q = request.GET.get("q", "").strip()
        if q:
            qs = (
                qs.filter(patient__first_name__icontains=q)
                | qs.filter(patient__last_name__icontains=q)
                | qs.filter(patient__hospital_number__icontains=q)
            )

        filter_val = request.GET.get("filter", "all")
        if filter_val == "due_soon":
            qs = qs.filter(edd__lte=today + timedelta(weeks=4))
        elif filter_val == "early":
            qs = qs.filter(edd__gte=today + timedelta(weeks=28))

        return render(request, self.template_name, {
            "records": qs,
            "today": today,
            "q": q,
            "filter_val": filter_val,
            "total_active": ANCRecord.objects.filter(is_active=True).count(),
            "due_soon_count": ANCRecord.objects.filter(
                is_active=True, edd__lte=today + timedelta(weeks=4)
            ).count(),
        })


# ── Create ANC Record ─────────────────────────────────────────

@method_decorator(login_required, name="dispatch")
class ANCRecordCreateView(View):
    template_name = "antenatal/record_form.html"

    def get(self, request):
        patient = self._get_patient(request)
        return render(request, self.template_name, {
            "form": ANCRecordForm(),
            "patient": patient,
            "action": "New",
        })

    def post(self, request):
        patient_pk = request.POST.get("patient")
        patient = get_object_or_404(Patient, pk=patient_pk) if patient_pk else None

        form = ANCRecordForm(request.POST)
        if not patient:
            form.add_error(None, "Please select a patient before saving.")

        if patient and form.is_valid():
            record = form.save(commit=False)
            record.patient = patient
            record.is_active = True
            record.save()
            messages.success(request, f"ANC record created for {patient.full_name}.")
            return redirect("antenatal:detail", pk=record.pk)

        return render(request, self.template_name, {
            "form": form,
            "patient": patient,
            "action": "New",
        })

    def _get_patient(self, request):
        pk = request.GET.get("patient")
        if pk:
            return Patient.objects.filter(pk=pk, is_active=True).first()
        return None


# ── Edit ANC Record ───────────────────────────────────────────

@method_decorator(login_required, name="dispatch")
class ANCRecordEditView(View):
    template_name = "antenatal/record_form.html"

    def get(self, request, pk):
        record = get_object_or_404(ANCRecord.objects.select_related("patient"), pk=pk)
        return render(request, self.template_name, {
            "form": ANCRecordForm(instance=record),
            "record": record,
            "patient": record.patient,
            "action": "Edit",
        })

    def post(self, request, pk):
        record = get_object_or_404(ANCRecord.objects.select_related("patient"), pk=pk)
        form = ANCRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            messages.success(request, "ANC record updated.")
            return redirect("antenatal:detail", pk=record.pk)
        return render(request, self.template_name, {
            "form": form,
            "record": record,
            "patient": record.patient,
            "action": "Edit",
        })


# ── Detail ────────────────────────────────────────────────────

@method_decorator(login_required, name="dispatch")
class ANCDetailView(View):
    template_name = "antenatal/detail.html"

    def get(self, request, pk):
        record = get_object_or_404(
            ANCRecord.objects.select_related("patient")
            .prefetch_related("visits", "scans"),
            pk=pk,
        )
        return render(request, self.template_name, {
            "record": record,
            "patient": record.patient,
            "today": date.today(),
        })


# ── Add Visit ────────────────────────────────────────────────

@method_decorator(login_required, name="dispatch")
class ANCVisitCreateView(View):
    template_name = "antenatal/visit_form.html"

    def get(self, request, pk):
        record = get_object_or_404(ANCRecord.objects.select_related("patient"), pk=pk)
        form = ANCVisitForm(initial={"gestational_age_weeks": record.gestational_age_weeks})
        return render(request, self.template_name, {
            "form": form,
            "record": record,
            "action": "Add",
        })

    def post(self, request, pk):
        record = get_object_or_404(ANCRecord.objects.select_related("patient"), pk=pk)
        form = ANCVisitForm(request.POST)
        if form.is_valid():
            visit = form.save(commit=False)
            visit.record = record
            visit.save()
            messages.success(request, f"Visit on {visit.visit_date} recorded.")
            return redirect("antenatal:detail", pk=record.pk)
        return render(request, self.template_name, {
            "form": form,
            "record": record,
            "action": "Add",
        })


# ── Edit Visit ───────────────────────────────────────────────

@method_decorator(login_required, name="dispatch")
class ANCVisitEditView(View):
    template_name = "antenatal/visit_form.html"

    def get(self, request, pk, visit_pk):
        record = get_object_or_404(ANCRecord.objects.select_related("patient"), pk=pk)
        visit = get_object_or_404(ANCVisit, pk=visit_pk, record=record)
        return render(request, self.template_name, {
            "form": ANCVisitForm(instance=visit),
            "record": record,
            "visit": visit,
            "action": "Edit",
        })

    def post(self, request, pk, visit_pk):
        record = get_object_or_404(ANCRecord.objects.select_related("patient"), pk=pk)
        visit = get_object_or_404(ANCVisit, pk=visit_pk, record=record)
        form = ANCVisitForm(request.POST, instance=visit)
        if form.is_valid():
            form.save()
            messages.success(request, "Visit updated.")
            return redirect("antenatal:detail", pk=record.pk)
        return render(request, self.template_name, {
            "form": form,
            "record": record,
            "visit": visit,
            "action": "Edit",
        })


# ── Add Scan ─────────────────────────────────────────────────

@method_decorator(login_required, name="dispatch")
class ObstetricScanCreateView(View):
    template_name = "antenatal/scan_form.html"

    def get(self, request, pk):
        record = get_object_or_404(ANCRecord.objects.select_related("patient"), pk=pk)
        form = ObstetricScanForm(initial={
            "gestational_age_weeks": record.gestational_age_weeks,
            "gestational_age_days":  record.gestational_age_days,
        })
        return render(request, self.template_name, {
            "form": form,
            "record": record,
            "action": "Add",
        })

    def post(self, request, pk):
        record = get_object_or_404(ANCRecord.objects.select_related("patient"), pk=pk)
        form = ObstetricScanForm(request.POST, request.FILES)
        if form.is_valid():
            scan = form.save(commit=False)
            scan.record = record
            scan.save()
            messages.success(request, f"Ultrasound scan on {scan.scan_date} saved.")
            return redirect("antenatal:detail", pk=record.pk)
        return render(request, self.template_name, {
            "form": form,
            "record": record,
            "action": "Add",
        })


# ── Edit Scan ────────────────────────────────────────────────

@method_decorator(login_required, name="dispatch")
class ObstetricScanEditView(View):
    template_name = "antenatal/scan_form.html"

    def get(self, request, pk, scan_pk):
        record = get_object_or_404(ANCRecord.objects.select_related("patient"), pk=pk)
        scan = get_object_or_404(ObstetricScan, pk=scan_pk, record=record)
        return render(request, self.template_name, {
            "form": ObstetricScanForm(instance=scan),
            "record": record,
            "scan": scan,
            "action": "Edit",
        })

    def post(self, request, pk, scan_pk):
        record = get_object_or_404(ANCRecord.objects.select_related("patient"), pk=pk)
        scan = get_object_or_404(ObstetricScan, pk=scan_pk, record=record)
        form = ObstetricScanForm(request.POST, request.FILES, instance=scan)
        if form.is_valid():
            form.save()
            messages.success(request, "Scan updated.")
            return redirect("antenatal:detail", pk=record.pk)
        return render(request, self.template_name, {
            "form": form,
            "record": record,
            "scan": scan,
            "action": "Edit",
        })


# ── Patient search (HTMX partial for ANC create form) ────────

@login_required
def anc_patient_search(request):
    """Returns a small HTML partial of matching patients with data-pk attributes,
    used by the ANC record create form's inline patient picker."""
    q = request.GET.get("q", "").strip()
    patients = []
    if q:
        patients = (
            Patient.objects.filter(is_active=True)
            .filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(hospital_number__icontains=q)
            )
            .order_by("last_name", "first_name")[:10]
        )
    return render(request, "antenatal/partials/patient_search_results.html", {
        "patients": patients,
        "q": q,
    })
