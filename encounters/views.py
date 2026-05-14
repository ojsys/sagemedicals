from django import forms as django_forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from core.forms import SmartSelectMixin
from encounters.models import Diagnosis, Encounter, Vitals
from patients.models import Patient
from scheduling.models import QueueEntry


class VitalsForm(SmartSelectMixin, django_forms.ModelForm):
    class Meta:
        model = Vitals
        fields = ["temperature", "bp_systolic", "bp_diastolic", "pulse",
                  "respiratory_rate", "spo2", "weight", "height", "pain_score"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs["class"] = "form-control"
            f.required = False


class DiagnosisForm(SmartSelectMixin, django_forms.ModelForm):
    class Meta:
        model = Diagnosis
        fields = ["icd10_code", "description", "diagnosis_type"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            if isinstance(f.widget, django_forms.Select):
                f.widget.attrs["class"] = "form-select"
            else:
                f.widget.attrs["class"] = "form-control"


class EncounterForm(SmartSelectMixin, django_forms.ModelForm):
    class Meta:
        model = Encounter
        fields = ["encounter_type", "chief_complaint", "history_of_presenting_illness",
                  "review_of_systems", "examination_findings", "assessment", "plan", "location"]
        widgets = {k: django_forms.Textarea(attrs={"rows": 3, "class": "form-control"})
                   for k in ["chief_complaint", "history_of_presenting_illness",
                              "review_of_systems", "examination_findings", "assessment", "plan"]}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["encounter_type"].widget.attrs["class"] = "form-select"
        self.fields["location"].widget.attrs["class"] = "form-control"


@method_decorator(login_required, name="dispatch")
class EncounterListView(View):
    template_name = "encounters/list.html"

    def get(self, request):
        from django.core.paginator import Paginator
        from antenatal.models import ANCVisit
        patient_pk = request.GET.get("patient")
        status_filter = request.GET.get("status", "")
        type_filter = request.GET.get("type", "")

        qs = (
            Encounter.objects.select_related("patient", "attending")
            .order_by("-date_time")
        )
        patient = None
        if patient_pk:
            patient = get_object_or_404(Patient, pk=patient_pk)
            qs = qs.filter(patient=patient)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if type_filter:
            qs = qs.filter(encounter_type=type_filter)

        paginator = Paginator(qs, 30)
        page = paginator.get_page(request.GET.get("page", 1))

        anc_qs = ANCVisit.objects.select_related("record__patient").order_by("-visit_date")
        if patient_pk:
            anc_qs = anc_qs.filter(record__patient=patient)
        if type_filter and type_filter != "anc":
            anc_qs = anc_qs.none()

        return render(request, self.template_name, {
            "encounters": page,
            "page_obj": page,
            "patient": patient,
            "status_filter": status_filter,
            "type_filter": type_filter,
            "status_choices": Encounter.Status.choices,
            "type_choices": Encounter.EncounterType.choices,
            "total": qs.count(),
            "anc_visits": anc_qs[:30],
            "anc_total": anc_qs.count(),
        })


@method_decorator(login_required, name="dispatch")
class EncounterCreateView(View):
    def post(self, request, patient_pk):
        patient = get_object_or_404(Patient, pk=patient_pk)
        queue_pk = request.POST.get("queue_entry")
        queue_entry = QueueEntry.objects.filter(pk=queue_pk).first() if queue_pk else None
        encounter = Encounter.objects.create(
            patient=patient,
            attending=request.user,
            date_time=timezone.now(),
            status=Encounter.Status.DRAFT,
            appointment=queue_entry,
        )
        if queue_entry:
            queue_entry.status = QueueEntry.QueueStatus.WITH_DOCTOR
            queue_entry.save(update_fields=["status"])
        # Auto-create draft invoice with consultation fee
        from billing.models import ServiceCatalogue
        from billing.services import add_invoice_item
        svc = ServiceCatalogue.objects.filter(category="consultation", is_active=True).first()
        if svc:
            price = svc.price_for_patient(patient)
            add_invoice_item(encounter, svc.name, price, service=svc)
        return redirect("encounters:workspace", pk=encounter.pk)


@method_decorator(login_required, name="dispatch")
class EncounterWorkspaceView(View):
    template_name = "encounters/workspace.html"

    def _ctx(self, encounter):
        from laboratory.models import LabOrder, LabTest
        return {
            "encounter": encounter,
            "patient": encounter.patient,
            "vitals_form": VitalsForm(instance=getattr(encounter, "vitals", None)),
            "diagnosis_form": DiagnosisForm(),
            "diagnoses": encounter.diagnoses.all(),
            "prescriptions": encounter.prescriptions.all().select_related("drug"),
            "lab_orders": encounter.lab_orders.all().select_related("test"),
            "lab_tests": LabTest.objects.filter(is_active=True).order_by("name"),
            "allergies": encounter.patient.active_allergies,
            "conditions": encounter.patient.chronic_conditions.filter(status="active"),
            "recent_labs": LabOrder.objects.filter(patient=encounter.patient, status="released")
                           .select_related("test", "result").order_by("-created_at")[:5],
        }

    def get(self, request, pk):
        encounter = get_object_or_404(Encounter, pk=pk)
        form = EncounterForm(instance=encounter)
        return render(request, self.template_name, {**self._ctx(encounter), "form": form})

    def post(self, request, pk):
        encounter = get_object_or_404(Encounter, pk=pk, status=Encounter.Status.DRAFT)
        form = EncounterForm(request.POST, instance=encounter)
        if form.is_valid():
            e = form.save(commit=False)
            e._current_user = request.user
            e.save()
            if request.headers.get("HX-Request"):
                return HttpResponse('<span class="text-success small"><i class="bi bi-check2 me-1"></i>Saved</span>')
            messages.success(request, "Encounter saved.")
        return render(request, self.template_name, {**self._ctx(encounter), "form": form})


@method_decorator(login_required, name="dispatch")
class EncounterSignView(View):
    def post(self, request, pk):
        encounter = get_object_or_404(Encounter, pk=pk, status=Encounter.Status.DRAFT)
        encounter.status = Encounter.Status.SIGNED
        encounter.signed_at = timezone.now()
        encounter.signed_by = request.user
        encounter._current_user = request.user
        encounter.save()
        # Release any ready lab results
        from scheduling.models import QueueEntry
        if encounter.appointment:
            encounter.appointment.status = QueueEntry.QueueStatus.COMPLETED
            encounter.appointment.save(update_fields=["status"])
        messages.success(request, "Encounter signed and locked.")
        return redirect("patients:detail", pk=encounter.patient.pk)


@method_decorator(login_required, name="dispatch")
class VitalsSaveView(View):
    def post(self, request, pk):
        encounter = get_object_or_404(Encounter, pk=pk)
        vitals, _ = Vitals.objects.get_or_create(encounter=encounter)
        form = VitalsForm(request.POST, instance=vitals)
        if form.is_valid():
            v = form.save(commit=False)
            v.recorded_by = request.user
            v._current_user = request.user
            v.save()
            if request.headers.get("HX-Request"):
                return render(request, "encounters/partials/vitals_display.html", {"vitals": v})
        return redirect("encounters:workspace", pk=pk)


@method_decorator(login_required, name="dispatch")
class DiagnosisAddView(View):
    def post(self, request, pk):
        encounter = get_object_or_404(Encounter, pk=pk, status=Encounter.Status.DRAFT)
        form = DiagnosisForm(request.POST)
        if form.is_valid():
            d = form.save(commit=False)
            d.encounter = encounter
            d.clinician = request.user
            d._current_user = request.user
            d.save()
        if request.headers.get("HX-Request"):
            return render(request, "encounters/partials/diagnosis_list.html",
                          {"diagnoses": encounter.diagnoses.all()})
        return redirect("encounters:workspace", pk=pk)


@method_decorator(login_required, name="dispatch")
class DiagnosisDeleteView(View):
    def post(self, request, pk, diag_pk):
        encounter = get_object_or_404(Encounter, pk=pk)
        Diagnosis.objects.filter(pk=diag_pk, encounter=encounter).delete()
        if request.headers.get("HX-Request"):
            return render(request, "encounters/partials/diagnosis_list.html",
                          {"diagnoses": encounter.diagnoses.all()})
        return redirect("encounters:workspace", pk=pk)
