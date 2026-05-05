from django import forms as django_forms
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from core.forms import SmartSelectMixin
from encounters.models import Encounter
from prescriptions.models import Drug, Prescription
from prescriptions.services import (
    check_allergy,
    check_interactions,
    get_active_prescriptions,
)


class PrescriptionForm(SmartSelectMixin, django_forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ["drug", "dose", "route", "frequency", "frequency_other",
                  "duration_days", "quantity", "instructions", "is_prn", "is_stat"]
        widgets = {"instructions": django_forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["drug"].queryset = Drug.objects.filter(is_formulary=True, is_active=True)
        self.fields["drug"].widget.attrs["class"] = "form-select"
        for name, f in self.fields.items():
            if name not in ("is_prn", "is_stat") and not isinstance(f.widget, django_forms.Select):
                f.widget.attrs.setdefault("class", "form-control")
            elif isinstance(f.widget, django_forms.Select):
                f.widget.attrs.setdefault("class", "form-select")


@method_decorator(login_required, name="dispatch")
class DrugSearchView(View):
    """HTMX typeahead — returns a datalist or option list."""

    def get(self, request):
        q = request.GET.get("q", "").strip()
        if len(q) < 2:
            return HttpResponse("")
        drugs = Drug.objects.filter(
            is_active=True, is_formulary=True
        ).filter(
            Q(generic_name__icontains=q) | Q(brand_name__icontains=q)
        )[:20]
        return render(request, "prescriptions/partials/drug_options.html", {"drugs": drugs})


@method_decorator(login_required, name="dispatch")
class PrescriptionCreateView(View):
    def post(self, request, encounter_pk):
        encounter = get_object_or_404(Encounter, pk=encounter_pk, status=Encounter.Status.DRAFT)
        form = PrescriptionForm(request.POST)
        if not form.is_valid():
            if request.headers.get("HX-Request"):
                return render(request, "prescriptions/partials/prescription_form.html",
                              {"form": form, "encounter": encounter})
            return redirect("encounters:workspace", pk=encounter_pk)

        drug = form.cleaned_data["drug"]
        patient = encounter.patient

        # Allergy check — hard stop
        allergy_hit = check_allergy(patient, drug)
        if allergy_hit and not request.POST.get("allergy_override"):
            if request.headers.get("HX-Request"):
                return render(request, "prescriptions/partials/allergy_block.html", {
                    "drug": drug, "allergy": allergy_hit, "encounter_pk": encounter_pk,
                    "post_data": request.POST,
                })
            return redirect("encounters:workspace", pk=encounter_pk)

        # Interaction check — soft warning
        active_rx = get_active_prescriptions(patient, exclude_encounter=encounter)
        interactions = check_interactions(drug, active_rx)
        severe = [i for i in interactions if i[1].severity in ("severe", "contraindicated")]
        if severe and not request.POST.get("interaction_override"):
            if request.headers.get("HX-Request"):
                return render(request, "prescriptions/partials/interaction_warning.html", {
                    "drug": drug, "interactions": severe, "encounter_pk": encounter_pk,
                    "post_data": request.POST,
                })

        rx = form.save(commit=False)
        rx.encounter = encounter
        rx.patient = patient
        rx.prescriber = request.user
        rx.allergy_override_reason = request.POST.get("allergy_override_reason", "")
        rx.interaction_override_reason = request.POST.get("interaction_override_reason", "")
        rx._current_user = request.user
        rx.save()

        # Add drug to invoice
        from billing.services import add_invoice_item
        add_invoice_item(encounter, f"{drug} × {rx.quantity}", 0)  # price set after dispensing

        if request.headers.get("HX-Request"):
            rxs = encounter.prescriptions.all().select_related("drug")
            return render(request, "prescriptions/partials/prescription_list.html",
                          {"prescriptions": rxs, "encounter": encounter})
        return redirect("encounters:workspace", pk=encounter_pk)


@method_decorator(login_required, name="dispatch")
class PrescriptionListView(View):
    template_name = "prescriptions/list.html"

    def get(self, request):
        from django.core.paginator import Paginator
        from patients.models import Patient

        status_filter = request.GET.get("status", "")
        search = request.GET.get("q", "").strip()
        patient_pk = request.GET.get("patient")

        qs = (
            Prescription.objects.select_related(
                "drug", "patient", "prescriber", "encounter"
            ).order_by("-created_at")
        )

        patient = None
        if patient_pk:
            patient = get_object_or_404(Patient, pk=patient_pk)
            qs = qs.filter(patient=patient)

        if status_filter:
            qs = qs.filter(status=status_filter)

        if search:
            qs = qs.filter(
                Q(patient__first_name__icontains=search)
                | Q(patient__last_name__icontains=search)
                | Q(patient__hospital_number__icontains=search)
                | Q(drug__generic_name__icontains=search)
                | Q(drug__brand_name__icontains=search)
            )

        total = qs.count()
        pending_count = Prescription.objects.filter(status=Prescription.Status.PENDING).count()
        dispensed_count = Prescription.objects.filter(status=Prescription.Status.DISPENSED).count()
        cancelled_count = Prescription.objects.filter(status=Prescription.Status.CANCELLED).count()

        paginator = Paginator(qs, 30)
        page = paginator.get_page(request.GET.get("page", 1))

        return render(request, self.template_name, {
            "prescriptions": page,
            "page_obj": page,
            "patient": patient,
            "status_filter": status_filter,
            "search": search,
            "total": total,
            "pending_count": pending_count,
            "dispensed_count": dispensed_count,
            "cancelled_count": cancelled_count,
            "status_choices": Prescription.Status.choices,
        })


@method_decorator(login_required, name="dispatch")
class PrescriptionCancelView(View):
    def post(self, request, pk):
        rx = get_object_or_404(Prescription, pk=pk, status=Prescription.Status.PENDING)
        rx.status = Prescription.Status.CANCELLED
        rx._current_user = request.user
        rx.save()
        if request.headers.get("HX-Request"):
            rxs = rx.encounter.prescriptions.all().select_related("drug")
            return render(request, "prescriptions/partials/prescription_list.html",
                          {"prescriptions": rxs, "encounter": rx.encounter})
        return redirect("encounters:workspace", pk=rx.encounter.pk)
