import json

from django import forms as django_forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from admissions.models import Admission, Bed, MedicationAdministration, Ward, WardRound
from core.forms import SmartSelectMixin
from patients.models import Patient


class AdmitForm(SmartSelectMixin, django_forms.Form):
    bed = django_forms.ModelChoiceField(
        queryset=Bed.objects.filter(status=Bed.Status.AVAILABLE).select_related(
            "room__ward"
        ),
        label="Bed",
        widget=django_forms.Select(attrs={"class": "form-select"}),
    )
    diagnosis_on_admission = django_forms.CharField(
        widget=django_forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        required=False,
        label="Admitting Diagnosis",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bed"].queryset = Bed.objects.filter(
            status=Bed.Status.AVAILABLE
        ).select_related("room__ward").order_by("room__ward__name", "room__name", "label")


class TransferForm(SmartSelectMixin, django_forms.Form):
    new_bed = django_forms.ModelChoiceField(
        queryset=Bed.objects.filter(status=Bed.Status.AVAILABLE),
        label="New Bed",
        widget=django_forms.Select(attrs={"class": "form-select"}),
    )
    reason = django_forms.CharField(
        widget=django_forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        required=False,
    )


class DischargeForm(SmartSelectMixin, django_forms.Form):
    discharge_type = django_forms.ChoiceField(
        choices=Admission.DischargeType.choices,
        widget=django_forms.Select(attrs={"class": "form-select"}),
    )
    discharge_summary = django_forms.CharField(
        widget=django_forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
        required=False,
    )


class WardRoundForm(SmartSelectMixin, django_forms.ModelForm):
    class Meta:
        model = WardRound
        fields = ["note", "vitals_note", "plan"]
        widgets = {
            "note": django_forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "vitals_note": django_forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            "plan": django_forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }


class MARForm(SmartSelectMixin, django_forms.ModelForm):
    class Meta:
        model = MedicationAdministration
        fields = ["prescription", "scheduled_at", "result", "dose_given", "notes"]
        widgets = {
            "scheduled_at": django_forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
            "notes": django_forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        }

    def __init__(self, *args, admission=None, **kwargs):
        super().__init__(*args, **kwargs)
        if admission:
            from prescriptions.models import Prescription
            self.fields["prescription"].queryset = Prescription.objects.filter(
                patient=admission.patient,
                status__in=["pending", "partially_dispensed"],
            ).select_related("drug")
        for name, f in self.fields.items():
            if isinstance(f.widget, django_forms.Select):
                f.widget.attrs.setdefault("class", "form-select")
            else:
                f.widget.attrs.setdefault("class", "form-control")


@method_decorator(login_required, name="dispatch")
class WardMapView(View):
    template_name = "admissions/ward_map.html"

    def get(self, request):
        import datetime
        from admissions.services import get_ward_bed_map
        from admissions.models import Bed as BedModel

        wards = Ward.objects.filter(is_active=True).prefetch_related("rooms__beds")
        ward_pk = request.GET.get("ward")
        ward = get_object_or_404(Ward, pk=ward_pk) if ward_pk else wards.first()

        bed_map = get_ward_bed_map(ward) if ward else []

        today = timezone.localdate()

        # Enrich bed_map with days_in for occupied beds
        for entry in bed_map:
            for item in entry["beds"]:
                if item["admission"]:
                    item["days_in"] = (today - item["admission"].admitted_at.date()).days
                else:
                    item["days_in"] = None

        # Global stats across all wards
        all_beds = BedModel.objects.filter(room__ward__is_active=True)
        total_beds     = all_beds.count()
        occupied_count = all_beds.filter(status=BedModel.Status.OCCUPIED).count()
        available_count= all_beds.filter(status=BedModel.Status.AVAILABLE).count()
        maintenance_count = all_beds.filter(status=BedModel.Status.MAINTENANCE).count()

        # Per-ward occupancy for tab badges — attach as plain attributes
        ward_list = []
        for w in wards:
            wb = BedModel.objects.filter(room__ward=w)
            w.occ = wb.filter(status=BedModel.Status.OCCUPIED).count()
            w.tot = wb.count()
            ward_list.append(w)

        # Per-ward stats for the current ward card
        if ward:
            wb = BedModel.objects.filter(room__ward=ward)
            ward.occ = wb.filter(status=BedModel.Status.OCCUPIED).count()
            ward.tot = wb.count()

        return render(request, self.template_name, {
            "wards": ward_list,
            "ward": ward,
            "bed_map": bed_map,
            "total_beds": total_beds,
            "occupied_count": occupied_count,
            "available_count": available_count,
            "maintenance_count": maintenance_count,
        })


@method_decorator(login_required, name="dispatch")
class AdmissionListView(View):
    template_name = "admissions/list.html"

    def get(self, request):
        import datetime
        ward_pk = request.GET.get("ward")
        status_filter = request.GET.get("status", "active")

        wards = Ward.objects.filter(is_active=True)
        qs = (
            Admission.objects.select_related(
                "patient", "bed__room__ward", "admitting_doctor"
            ).order_by("-admitted_at")
        )

        if status_filter:
            qs = qs.filter(status=status_filter)
        if ward_pk:
            qs = qs.filter(bed__room__ward_id=ward_pk)

        today = timezone.localdate()
        admissions = []
        for a in qs:
            days = (today - a.admitted_at.date()).days
            admissions.append({"admission": a, "days_in": days})

        active_count      = Admission.objects.filter(status="active").count()
        discharged_today  = Admission.objects.filter(
            status="discharged",
            discharged_at__date=today,
        ).count()

        return render(request, self.template_name, {
            "admissions": admissions,
            "wards": wards,
            "ward_pk": ward_pk,
            "status_filter": status_filter,
            "active_count": active_count,
            "discharged_today": discharged_today,
            "total_beds": Bed.objects.filter(room__ward__is_active=True).count(),
            "occupied_count": Bed.objects.filter(status=Bed.Status.OCCUPIED).count(),
        })


@method_decorator(login_required, name="dispatch")
class AdmitPatientView(View):
    template_name = "admissions/admit.html"

    def get(self, request, patient_pk):
        patient = get_object_or_404(Patient, pk=patient_pk)
        form = AdmitForm()
        wards = Ward.objects.filter(is_active=True).prefetch_related(
            "rooms__beds"
        ).order_by("name")
        ward_data = []
        for w in wards:
            rooms = []
            for room in w.rooms.all():
                beds = [
                    {"id": b.pk, "label": b.label, "status": b.status}
                    for b in room.beds.all()
                ]
                rooms.append({"name": room.name, "is_isolation": room.is_isolation, "beds": beds})
            ward_data.append({"id": w.pk, "name": w.name, "rooms": rooms})
        return render(request, self.template_name, {
            "patient": patient,
            "form": form,
            "ward_data_json": json.dumps(ward_data),
        })

    def post(self, request, patient_pk):
        patient = get_object_or_404(Patient, pk=patient_pk)
        form = AdmitForm(request.POST)
        if form.is_valid():
            from admissions.services import admit_patient
            try:
                admit_patient(
                    patient=patient,
                    bed=form.cleaned_data["bed"],
                    admitting_doctor=request.user,
                    diagnosis=form.cleaned_data["diagnosis_on_admission"],
                    user=request.user,
                )
                messages.success(request, f"{patient.full_name} admitted successfully.")
                return redirect("patients:detail", pk=patient_pk)
            except ValueError as e:
                messages.error(request, str(e))
        return render(request, self.template_name, {"patient": patient, "form": form})


@method_decorator(login_required, name="dispatch")
class AdmissionDetailView(View):
    template_name = "admissions/detail.html"

    def _ctx(self, admission):
        days_admitted = (timezone.localdate() - admission.admitted_at.date()).days
        return {
            "admission": admission,
            "patient": admission.patient,
            "days_admitted": days_admitted,
            "ward_rounds": admission.ward_rounds.select_related("clinician").all()[:20],
            "round_form": WardRoundForm(),
            "mar_entries": admission.mar_entries.select_related(
                "prescription__drug", "administered_by"
            ).order_by("-scheduled_at")[:30],
            "mar_form": MARForm(admission=admission),
            "transfers": admission.transfers.select_related(
                "from_bed__room__ward", "to_bed__room__ward", "transferred_by"
            ),
            "available_beds": Bed.objects.filter(
                status=Bed.Status.AVAILABLE
            ).select_related("room__ward").order_by("room__ward__name", "label"),
        }

    def get(self, request, pk):
        admission = get_object_or_404(Admission, pk=pk)
        return render(request, self.template_name, self._ctx(admission))


@method_decorator(login_required, name="dispatch")
class TransferBedView(View):
    def post(self, request, pk):
        admission = get_object_or_404(Admission, pk=pk, status=Admission.Status.ACTIVE)
        form = TransferForm(request.POST)
        if form.is_valid():
            from admissions.services import transfer_bed
            try:
                transfer_bed(
                    admission=admission,
                    new_bed=form.cleaned_data["new_bed"],
                    transferred_by=request.user,
                    reason=form.cleaned_data["reason"],
                    user=request.user,
                )
                messages.success(request, "Bed transfer completed.")
            except ValueError as e:
                messages.error(request, str(e))
        return redirect("admissions:detail", pk=pk)


@method_decorator(login_required, name="dispatch")
class DischargeView(View):
    template_name = "admissions/discharge.html"

    def get(self, request, pk):
        admission = get_object_or_404(Admission, pk=pk, status=Admission.Status.ACTIVE)
        form = DischargeForm()
        return render(request, self.template_name, {"admission": admission, "form": form})

    def post(self, request, pk):
        admission = get_object_or_404(Admission, pk=pk, status=Admission.Status.ACTIVE)
        form = DischargeForm(request.POST)
        if form.is_valid():
            from admissions.services import discharge_patient
            try:
                discharge_patient(
                    admission=admission,
                    discharge_type=form.cleaned_data["discharge_type"],
                    summary=form.cleaned_data["discharge_summary"],
                    discharged_by=request.user,
                    user=request.user,
                )
                messages.success(
                    request,
                    f"{admission.patient.full_name} discharged successfully.",
                )
                return redirect("patients:detail", pk=admission.patient.pk)
            except ValueError as e:
                messages.error(request, str(e))
        return render(request, self.template_name, {"admission": admission, "form": form})


@method_decorator(login_required, name="dispatch")
class WardRoundAddView(View):
    def post(self, request, pk):
        admission = get_object_or_404(Admission, pk=pk, status=Admission.Status.ACTIVE)
        form = WardRoundForm(request.POST)
        if form.is_valid():
            rnd = form.save(commit=False)
            rnd.admission = admission
            rnd.clinician = request.user
            rnd._current_user = request.user
            rnd.save()
            messages.success(request, "Ward round note saved.")
        return redirect("admissions:detail", pk=pk)


@method_decorator(login_required, name="dispatch")
class MARAddView(View):
    def post(self, request, pk):
        admission = get_object_or_404(Admission, pk=pk, status=Admission.Status.ACTIVE)
        form = MARForm(request.POST, admission=admission)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.admission = admission
            entry.administered_by = request.user
            entry.administered_at = timezone.now()
            entry._current_user = request.user
            entry.save()
            messages.success(request, "Administration recorded.")
        return redirect("admissions:detail", pk=pk)
