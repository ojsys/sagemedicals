from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from patients.forms import (
    AllergyForm,
    ChronicConditionForm,
    NextOfKinForm,
    PatientRegistrationForm,
    PatientSearchForm,
)
from patients.models import Allergy, Patient
from patients.services import find_duplicates, generate_hospital_number


@method_decorator(login_required, name="dispatch")
class PatientSearchView(View):
    template_name = "patients/search.html"
    partial_template = "patients/partials/search_results.html"

    def get(self, request):
        from admissions.models import Admission
        from scheduling.models import QueueEntry
        from django.utils import timezone

        form = PatientSearchForm(request.GET or None)
        query = request.GET.get("q", "").strip()
        filter_type = request.GET.get("filter", "all")

        base_qs = Patient.objects.filter(is_active=True).prefetch_related("allergies")

        admitted_pks = Admission.objects.filter(
            status=Admission.Status.ACTIVE
        ).values_list("patient_id", flat=True)

        ae_pks = QueueEntry.objects.filter(
            date=timezone.localdate(),
            clinic__name="Emergency Department",
        ).values_list("patient_id", flat=True)

        if query:
            qs = self._search(query)
            if filter_type == "inpatient":
                qs = qs.filter(pk__in=admitted_pks)
            elif filter_type == "outpatient":
                qs = qs.exclude(pk__in=admitted_pks)
            elif filter_type == "ae":
                qs = qs.filter(pk__in=ae_pks)
        else:
            if filter_type == "inpatient":
                qs = base_qs.filter(pk__in=admitted_pks).order_by("last_name", "first_name")
            elif filter_type == "outpatient":
                qs = base_qs.exclude(pk__in=admitted_pks).order_by("last_name", "first_name")
            elif filter_type == "ae":
                qs = base_qs.filter(pk__in=ae_pks).order_by("last_name", "first_name")
            else:
                qs = base_qs.order_by("last_name", "first_name")

        paginator = Paginator(qs, 25)
        page = paginator.get_page(request.GET.get("page", 1))
        total_count = Patient.objects.filter(is_active=True).count()

        ctx = {
            "form": form,
            "patients": page,
            "query": query,
            "total_count": total_count,
            "page_obj": page,
            "filter_type": filter_type,
            "inpatient_count": len(admitted_pks),
            "ae_count": len(ae_pks),
        }

        if request.headers.get("HX-Request"):
            return render(request, self.partial_template, ctx)

        return render(request, self.template_name, ctx)

    def _search(self, query):
        return Patient.objects.filter(
            Q(hospital_number__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(phone__icontains=query)
            | Q(phone_alt__icontains=query)
            | Q(nhia_number__icontains=query)
            | Q(email__icontains=query)
        ).filter(is_active=True).select_related().prefetch_related("allergies")[:50]


@method_decorator(login_required, name="dispatch")
class PatientRegisterView(View):
    template_name = "patients/register.html"

    def get(self, request):
        return render(request, self.template_name, {
            "form": PatientRegistrationForm(prefix="pt"),
            "nok_form": NextOfKinForm(prefix="nok"),
        })

    def post(self, request):
        form = PatientRegistrationForm(request.POST, request.FILES, prefix="pt")
        nok_form = NextOfKinForm(request.POST, prefix="nok")

        if form.is_valid() and nok_form.is_valid():
            # Final duplicate check before saving
            definite, _ = find_duplicates(
                form.cleaned_data["first_name"],
                form.cleaned_data["last_name"],
                form.cleaned_data["date_of_birth"],
                form.cleaned_data.get("phone", ""),
            )
            if definite.exists() and not request.POST.get("confirm_duplicate"):
                return render(request, self.template_name, {
                    "form": form,
                    "nok_form": nok_form,
                    "definite_duplicates": definite,
                    "show_duplicate_modal": True,
                })

            patient = form.save(commit=False)
            patient.hospital_number = generate_hospital_number()
            patient._current_user = request.user
            patient.save()

            nok = nok_form.save(commit=False)
            nok.patient = patient
            nok._current_user = request.user
            nok.save()

            messages.success(request, f"Patient registered: {patient.full_name} — {patient.hospital_number}")
            return redirect("patients:detail", pk=patient.pk)

        return render(request, self.template_name, {"form": form, "nok_form": nok_form})


@method_decorator(login_required, name="dispatch")
class PatientDetailView(View):
    template_name = "patients/detail.html"

    def get(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk, is_active=True)
        return render(request, self.template_name, {
            "patient": patient,
            "allergies": patient.allergies.all(),
            "conditions": patient.chronic_conditions.all(),
            "allergy_form": AllergyForm(),
            "condition_form": ChronicConditionForm(),
        })


@method_decorator(login_required, name="dispatch")
class PatientUpdateView(View):
    template_name = "patients/update.html"

    def get(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk, is_active=True)
        nok = getattr(patient, "next_of_kin", None)
        return render(request, self.template_name, {
            "patient": patient,
            "form": PatientRegistrationForm(instance=patient, prefix="pt"),
            "nok_form": NextOfKinForm(instance=nok, prefix="nok"),
        })

    def post(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk, is_active=True)
        nok = getattr(patient, "next_of_kin", None)
        form = PatientRegistrationForm(request.POST, request.FILES, instance=patient, prefix="pt")
        nok_form = NextOfKinForm(request.POST, instance=nok, prefix="nok")
        if form.is_valid() and nok_form.is_valid():
            p = form.save(commit=False)
            p._current_user = request.user
            p.save()
            n = nok_form.save(commit=False)
            n.patient = patient
            n._current_user = request.user
            n.save()
            messages.success(request, "Patient record updated.")
            return redirect("patients:detail", pk=patient.pk)
        return render(request, self.template_name, {"patient": patient, "form": form, "nok_form": nok_form})


@method_decorator(login_required, name="dispatch")
class DuplicateCheckView(View):
    """HTMX endpoint — fires on blur from first_name/last_name/dob fields."""

    def get(self, request):
        first = request.GET.get("first_name", "")
        last = request.GET.get("last_name", "")
        dob = request.GET.get("date_of_birth", "")
        phone = request.GET.get("phone", "")

        if not (first and last and dob):
            return HttpResponse("")

        try:
            from datetime import date
            dob_date = date.fromisoformat(dob)
        except ValueError:
            return HttpResponse("")

        definite, possible = find_duplicates(first, last, dob_date, phone)
        if not definite.exists() and not possible.exists():
            return HttpResponse(
                '<div style="display:flex;align-items:center;gap:8px;font-size:13px;'
                'color:var(--sage-green);padding:4px 0">'
                '<i class="bi bi-check-circle-fill" style="font-size:14px"></i>'
                'No matches found.</div>'
            )

        return render(request, "patients/partials/duplicate_alert.html", {
            "definite": definite,
            "possible": possible,
        })


@method_decorator(login_required, name="dispatch")
class AllergyCreateView(View):
    def post(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk, is_active=True)
        form = AllergyForm(request.POST)
        if form.is_valid():
            a = form.save(commit=False)
            a.patient = patient
            a._current_user = request.user
            a.save()
            if request.headers.get("HX-Request"):
                allergies = patient.allergies.all()
                return render(request, "patients/partials/allergy_list.html", {
                    "patient": patient,
                    "allergies": allergies,
                })
            messages.success(request, f"Allergy '{a.allergen}' added.")
        return redirect("patients:detail", pk=pk)


@method_decorator(login_required, name="dispatch")
class AllergyDeleteView(View):
    def post(self, request, pk, allergy_pk):
        allergy = get_object_or_404(Allergy, pk=allergy_pk, patient_id=pk)
        allergy.is_active = False
        allergy._current_user = request.user
        allergy.save()
        if request.headers.get("HX-Request"):
            allergies = allergy.patient.allergies.all()
            return render(request, "patients/partials/allergy_list.html", {
                "patient": allergy.patient,
                "allergies": allergies,
            })
        return redirect("patients:detail", pk=pk)


@method_decorator(login_required, name="dispatch")
class ConditionCreateView(View):
    def post(self, request, pk):
        patient = get_object_or_404(Patient, pk=pk, is_active=True)
        form = ChronicConditionForm(request.POST)
        if form.is_valid():
            c = form.save(commit=False)
            c.patient = patient
            c._current_user = request.user
            c.save()
            if request.headers.get("HX-Request"):
                conditions = patient.chronic_conditions.all()
                return render(request, "patients/partials/condition_list.html", {
                    "patient": patient, "conditions": conditions,
                })
            messages.success(request, f"Condition '{c.description}' added.")
        return redirect("patients:detail", pk=pk)
