from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_sameorigin

from accounts.models import Role
from antenatal.models import ANCRecord
from patients.models import Patient

from .certificate import build_birth_certificate_pdf
from .forms import BirthRecordForm
from .models import BirthRecord

# Keep in sync with the "Birth Certificates" link in templates/base/_sidebar_nav.html.
BIRTH_REGISTER_ROLES = frozenset({
    Role.SUPER_ADMIN, Role.HOSPITAL_ADMIN,
    Role.DOCTOR, Role.RESIDENT, Role.NURSE, Role.CHEW,
    Role.RECORDS_OFFICER,
})


class BirthRegisterAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Clinical staff who attend deliveries, plus records and hospital admin."""

    def test_func(self):
        u = self.request.user
        return bool(u.is_superuser or getattr(u, "role", None) in BIRTH_REGISTER_ROLES)

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("You don't have access to the birth register.")
        return super().handle_no_permission()


# ── Register (list) ──────────────────────────────────────────

class BirthListView(BirthRegisterAccessMixin, View):
    template_name = "births/list.html"

    def get(self, request):
        qs = BirthRecord.objects.select_related("mother", "attended_by")

        q = request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(child_first_name__icontains=q)
                | Q(child_surname__icontains=q)
                | Q(certificate_number__icontains=q)
                | Q(mother__first_name__icontains=q)
                | Q(mother__last_name__icontains=q)
                | Q(mother__hospital_number__icontains=q)
            )

        today = timezone.localdate()
        page = Paginator(qs, 50).get_page(request.GET.get("page"))
        return render(request, self.template_name, {
            "page": page,
            "records": page.object_list,
            "q": q,
            "total": BirthRecord.objects.count(),
            "this_month": BirthRecord.objects.filter(
                date_of_birth__year=today.year, date_of_birth__month=today.month,
            ).count(),
        })


# ── Register a birth ─────────────────────────────────────────

class BirthCreateView(BirthRegisterAccessMixin, View):
    template_name = "births/form.html"

    def get(self, request):
        anc = self._get_anc(request.GET.get("anc"))
        mother = anc.patient if anc else self._get_mother(request.GET.get("mother"))
        form = BirthRecordForm(initial=self._initial_from_anc(anc))
        return self._render(request, form, mother, anc)

    def post(self, request):
        mother_pk = request.POST.get("mother")
        mother = get_object_or_404(Patient, pk=mother_pk) if mother_pk else None
        anc = self._get_anc(request.POST.get("anc_record"))
        if anc and mother and anc.patient_id != mother.pk:
            anc = None

        form = BirthRecordForm(request.POST)
        if not mother:
            form.add_error(None, "Please select the mother before saving.")

        if mother and form.is_valid():
            record = form.save(commit=False)
            record.mother = mother
            record.anc_record = anc
            record.created_by = record.updated_by = request.user
            record._current_user = request.user
            record.save()
            messages.success(
                request,
                f"Birth registered — certificate {record.certificate_number} is ready to print.",
            )
            return redirect("births:detail", pk=record.pk)

        return self._render(request, form, mother, anc)

    def _render(self, request, form, mother, anc):
        return render(request, self.template_name, {
            "form": form,
            "mother": mother,
            "anc": anc,
            "action": "Register",
        })

    @staticmethod
    def _get_anc(pk):
        if not (pk and str(pk).isdigit()):
            return None
        return ANCRecord.objects.select_related("patient").filter(pk=pk).first()

    @staticmethod
    def _get_mother(pk):
        if not (pk and str(pk).isdigit()):
            return None
        return Patient.objects.filter(pk=pk, is_active=True).first()

    @staticmethod
    def _initial_from_anc(anc):
        """Pre-fill the form from a concluded pregnancy so staff only add the baby's details."""
        if not anc:
            return {}
        babies = anc.babies_count or 1
        initial = {"babies_in_delivery": babies, "delivery_mode": anc.delivery_mode}
        if anc.outcome_date:
            initial["date_of_birth"] = anc.outcome_date
            initial["gestational_age_weeks"] = anc.gestational_age_on(anc.outcome_date)
        already_registered = anc.birth_records.count()
        if already_registered:
            initial["birth_order"] = min(already_registered + 1, babies)
        return initial


# ── Edit ─────────────────────────────────────────────────────

class BirthEditView(BirthRegisterAccessMixin, View):
    template_name = "births/form.html"

    def get(self, request, pk):
        record = get_object_or_404(BirthRecord.objects.select_related("mother"), pk=pk)
        return self._render(request, BirthRecordForm(instance=record), record)

    def post(self, request, pk):
        record = get_object_or_404(BirthRecord.objects.select_related("mother"), pk=pk)
        form = BirthRecordForm(request.POST, instance=record)
        if form.is_valid():
            record = form.save(commit=False)
            record.updated_by = request.user
            record._current_user = request.user
            record.save()
            messages.success(request, "Birth record updated.")
            return redirect("births:detail", pk=record.pk)
        return self._render(request, form, record)

    def _render(self, request, form, record):
        return render(request, self.template_name, {
            "form": form,
            "record": record,
            "mother": record.mother,
            "anc": record.anc_record,
            "action": "Edit",
        })


# ── Detail ───────────────────────────────────────────────────

class BirthDetailView(BirthRegisterAccessMixin, View):
    template_name = "births/detail.html"

    def get(self, request, pk):
        record = get_object_or_404(
            BirthRecord.objects.select_related("mother", "anc_record", "attended_by", "created_by"),
            pk=pk,
        )
        return render(request, self.template_name, {"record": record})


# ── Certificate PDF ──────────────────────────────────────────

@method_decorator(xframe_options_sameorigin, name="dispatch")  # previewed in an iframe on the detail page
class BirthCertificatePDFView(BirthRegisterAccessMixin, View):
    def get(self, request, pk):
        record = get_object_or_404(
            BirthRecord.objects.select_related("mother", "attended_by"), pk=pk,
        )
        buf = build_birth_certificate_pdf(record)
        disposition = "attachment" if request.GET.get("download") else "inline"
        filename = f"birth-certificate-{record.certificate_number.replace('/', '-')}.pdf"
        response = HttpResponse(buf.read(), content_type="application/pdf")
        response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
        return response
