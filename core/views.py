import json
import time
from datetime import date

from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.contrib.auth.mixins import AccessMixin
from accounts.models import NURSING_ROLES, Role
from django.contrib.auth.mixins import AccessMixin
from django.template.defaultfilters import pluralize


@never_cache
@require_GET
def health_check(request):
    """
    /health/ — lightweight liveness + readiness probe.
    Returns 200 OK with JSON when everything is up, 503 on DB failure.
    Used by cPanel uptime monitors and load balancers.
    """
    checks = {}
    overall_ok = True

    # Database ping
    t0 = time.monotonic()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["db"] = {"ok": True, "latency_ms": round((time.monotonic() - t0) * 1000, 1)}
    except Exception as exc:
        checks["db"] = {"ok": False, "error": str(exc)}
        overall_ok = False

    # Cache ping
    t0 = time.monotonic()
    try:
        from django.core.cache import cache
        cache.set("_healthcheck", "1", timeout=5)
        val = cache.get("_healthcheck")
        checks["cache"] = {
            "ok": val == "1",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
        }
        if not checks["cache"]["ok"]:
            overall_ok = False
    except Exception as exc:
        checks["cache"] = {"ok": False, "error": str(exc)}
        overall_ok = False

    status = 200 if overall_ok else 503
    return JsonResponse(
        {"status": "ok" if overall_ok else "degraded", "checks": checks},
        status=status,
    )


class LandingView(View):
    """Public landing page. Handles staff sign-in; redirects authenticated users to the dashboard."""

    template_name = "core/landing.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(reverse("core:dashboard"))
        return render(request, self.template_name)

    def post(self, request):
        if request.user.is_authenticated:
            return redirect(reverse("core:dashboard"))

        email = request.POST.get("login", "").strip()
        password = request.POST.get("password", "")

        # ModelBackend resolves username → User.USERNAME_FIELD (email)
        user = authenticate(request, username=email, password=password)

        if user is not None and user.is_active:
            auth_login(request, user)
            # Honour 2FA — send to verify if a confirmed device exists
            from django_otp.plugins.otp_totp.models import TOTPDevice
            if TOTPDevice.objects.filter(user=user, confirmed=True).exists():
                return redirect(reverse("accounts:2fa_verify"))
            return redirect(reverse("core:dashboard"))

        return render(request, self.template_name, {
            "login_error": True,
            "login_email": email,
        })


@method_decorator(login_required, name="dispatch")
class TutorialView(View):
    template_name = "core/tutorial.html"

    def get(self, request):
        return render(request, self.template_name)


@method_decorator(login_required, name="dispatch")
class DashboardView(AccessMixin, View):
    template_name = "core/dashboard.html"
    nursing_template_name = "core/dashboard_nursing.html"
    role_template_name = "core/dashboard_role.html"

    # Roles that are allowed to access the staff EMR dashboard
    _STAFF_ROLES = frozenset(Role) - {Role.PATIENT}

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if getattr(request.user, "role", None) not in self._STAFF_ROLES:
            return redirect(reverse("portal:dashboard"))

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        role = getattr(request.user, "role", None)

        # Role-focused dashboards — each builds only the data its role needs.
        role_builders = {
            Role.LAB_TECH: self._lab_context,
            Role.RADIOLOGIST: self._lab_context,
            Role.PHARMACIST: self._pharmacy_context,
            Role.BILLING_OFFICER: self._billing_context,
            Role.RECEPTIONIST: self._reception_context,
            Role.RECORDS_OFFICER: self._records_context,
        }
        builder = role_builders.get(role)
        if builder:
            template, ctx = builder(request)
            return render(request, template, ctx)

        template = (
            self.nursing_template_name if role in NURSING_ROLES else self.template_name
        )
        return render(request, template, self._clinical_context(request))

    # ── Clinical / admin overview (doctors, residents, nurses, CHEWs, admins) ──
    def _clinical_context(self, request):
        today = date.today()

        from admissions.models import Admission
        from antenatal.models import ANCRecord, ANCVisit
        from encounters.models import Encounter
        from laboratory.models import LabOrder
        from patients.models import Patient
        from scheduling.models import Appointment, QueueEntry

        enc_pids = set(
            Encounter.objects.filter(date_time__date=today).values_list("patient_id", flat=True)
        )
        anc_pids = set(
            ANCVisit.objects.filter(visit_date=today).values_list("record__patient_id", flat=True)
        )
        patients_today = len(enc_pids | anc_pids)

        active_admissions = Admission.objects.filter(
            status=Admission.Status.ACTIVE
        ).count()

        queue_waiting = QueueEntry.objects.filter(
            date=today,
            status__in=[QueueEntry.QueueStatus.WAITING, QueueEntry.QueueStatus.WITH_DOCTOR],
        ).count()

        pending_labs = LabOrder.objects.filter(
            status__in=["ordered", "in_progress"]
        ).count()

        queue_today = (
            QueueEntry.objects.filter(date=today)
            .select_related("patient", "clinic", "triage_nurse")
            .order_by("arrived_at")[:25]
        )

        appointments_today = (
            Appointment.objects.filter(
                date=today,
                status__in=["scheduled", "checked_in"],
            )
            .select_related("patient", "clinic")
            .order_by("slot_time")[:20]
        )

        recent_patients = (
            Patient.objects.filter(is_active=True)
            .order_by("-created_at")[:8]
        )

        recent_admissions = (
            Admission.objects.filter(status=Admission.Status.ACTIVE)
            .select_related("patient", "bed__room__ward", "admitting_doctor")
            .order_by("-admitted_at")[:8]
        )

        from datetime import timedelta
        active_anc_count = ANCRecord.objects.filter(is_active=True).count()
        anc_due_soon_count = ANCRecord.objects.filter(
            is_active=True, edd__lte=today + timedelta(weeks=4)
        ).count()
        anc_dashboard_list = (
            ANCRecord.objects.filter(is_active=True)
            .select_related("patient")
            .prefetch_related("visits")
            .order_by("edd")[:10]
        )

        return {
            "today": today,
            "patients_today": patients_today,
            "active_admissions": active_admissions,
            "queue_waiting": queue_waiting,
            "pending_labs": pending_labs,
            "queue_today": queue_today,
            "appointments_today": appointments_today,
            "recent_patients": recent_patients,
            "recent_admissions": recent_admissions,
            "active_anc_count": active_anc_count,
            "anc_due_soon_count": anc_due_soon_count,
            "anc_dashboard_list": anc_dashboard_list,
        }

    # ── Laboratory (lab scientists / radiologists) ──
    def _lab_context(self, request):
        from laboratory.models import LabOrder
        S = LabOrder.Status
        today = date.today()

        active_states = [S.ORDERED, S.SAMPLE_COLLECTED, S.IN_PROGRESS, S.RESULTED]
        awaiting_collection = LabOrder.objects.filter(status=S.ORDERED).count()
        in_progress = LabOrder.objects.filter(
            status__in=[S.SAMPLE_COLLECTED, S.IN_PROGRESS]
        ).count()
        awaiting_verification = LabOrder.objects.filter(status=S.RESULTED).count()
        released_today = LabOrder.objects.filter(
            status__in=[S.VERIFIED, S.RELEASED], updated_at__date=today
        ).count()

        worklist = (
            LabOrder.objects.filter(status__in=active_states)
            .select_related("patient", "test", "ordering_clinician")
            .order_by("-priority", "created_at")[:25]
        )

        ctx = {
            "today": today,
            "eyebrow": "Laboratory",
            "page_title_text": "Laboratory",
            "subtitle": f"{awaiting_collection} sample{pluralize(awaiting_collection)} to collect · "
                        f"{awaiting_verification} result{pluralize(awaiting_verification)} awaiting verification.",
            "actions": [
                {"label": "Worklist", "href": reverse("laboratory:worklist"), "icon": "bi-clipboard-pulse", "primary": True},
                {"label": "Test Catalogue", "href": reverse("laboratory:test_catalogue"), "icon": "bi-card-list"},
            ],
            "stats": [
                {"label": "Awaiting Collection", "value": awaiting_collection, "tag": "Live", "meta": "samples to draw",
                 "icon": "bi-eyedropper", "glyph_style": "background:var(--sage-amber-soft);color:var(--sage-amber)"},
                {"label": "In Progress", "value": in_progress, "tag": "Live", "meta": "on the analyser",
                 "icon": "bi-hourglass-split", "glyph_style": ""},
                {"label": "Awaiting Verification", "value": awaiting_verification, "tag": "Action", "meta": "results to verify",
                 "icon": "bi-patch-check", "glyph_style": "background:var(--sage-red-soft);color:var(--sage-red)"},
                {"label": "Released Today", "value": released_today, "tag": "Today", "meta": "results released",
                 "icon": "bi-send-check", "glyph_style": "background:var(--sage-teal-soft);color:var(--sage-teal)"},
            ],
            "panel_template": "core/panels/lab_worklist.html",
            "worklist": worklist,
        }
        return self.role_template_name, ctx

    # ── Pharmacy (pharmacists) ──
    def _pharmacy_context(self, request):
        import datetime
        from django.db.models import F
        from prescriptions.models import Prescription
        from pharmacy.models import DrugBatch, StockLevel
        today = date.today()

        pending_rx = (
            Prescription.objects.filter(status=Prescription.Status.PENDING)
            .select_related("drug", "patient", "encounter")
            .order_by("created_at")[:25]
        )
        pending_count = Prescription.objects.filter(status=Prescription.Status.PENDING).count()
        dispensed_today = Prescription.objects.filter(
            status=Prescription.Status.DISPENSED, updated_at__date=today
        ).count()

        low_stock = (
            StockLevel.objects.filter(quantity_on_hand__lte=F("reorder_level"))
            .select_related("drug", "store")
            .order_by("quantity_on_hand")[:12]
        )
        low_stock_count = StockLevel.objects.filter(quantity_on_hand__lte=F("reorder_level")).count()
        near_expiry_count = DrugBatch.objects.filter(
            expiry_date__lte=today + datetime.timedelta(days=90),
            expiry_date__gte=today,
            quantity_remaining__gt=0,
        ).count()

        ctx = {
            "today": today,
            "eyebrow": "Pharmacy",
            "page_title_text": "Pharmacy",
            "subtitle": f"{pending_count} prescription{pluralize(pending_count)} awaiting dispensing · "
                        f"{low_stock_count} item{pluralize(low_stock_count)} low on stock.",
            "actions": [
                {"label": "Drug Inventory", "href": reverse("pharmacy:stock"), "icon": "bi-boxes"},
                {"label": "Receive Goods", "href": reverse("pharmacy:receive"), "icon": "bi-box-arrow-in-down"},
                {"label": "Pharmacy", "href": reverse("pharmacy:dashboard"), "icon": "bi-prescription2", "primary": True},
            ],
            "stats": [
                {"label": "To Dispense", "value": pending_count, "tag": "Action", "meta": "pending prescriptions",
                 "icon": "bi-capsule", "glyph_style": "background:var(--sage-amber-soft);color:var(--sage-amber)"},
                {"label": "Dispensed Today", "value": dispensed_today, "tag": "Today", "meta": "prescriptions filled",
                 "icon": "bi-bag-check", "glyph_style": "background:var(--sage-teal-soft);color:var(--sage-teal)"},
                {"label": "Low Stock", "value": low_stock_count, "tag": "Reorder", "meta": "at or below reorder level",
                 "icon": "bi-exclamation-triangle", "glyph_style": "background:var(--sage-red-soft);color:var(--sage-red)"},
                {"label": "Near Expiry", "value": near_expiry_count, "tag": "≤90d", "meta": "batches expiring soon",
                 "icon": "bi-calendar-x", "glyph_style": ""},
            ],
            "panel_template": "core/panels/pharmacy_queue.html",
            "pending_rx": pending_rx,
            "low_stock": low_stock,
        }
        return self.role_template_name, ctx

    # ── Billing (billing officers / cashiers) ──
    def _billing_context(self, request):
        from django.db.models import Sum
        from billing.models import Invoice, Payment
        today = date.today()

        unpaid_states = [Invoice.Status.ISSUED, Invoice.Status.PARTIAL]
        unpaid = Invoice.objects.filter(status__in=unpaid_states)
        unpaid_count = unpaid.count()
        outstanding = unpaid.aggregate(s=Sum("balance"))["s"] or 0
        paid_today = Payment.objects.filter(received_at__date=today).aggregate(s=Sum("amount"))["s"] or 0
        draft_count = Invoice.objects.filter(status=Invoice.Status.DRAFT).count()

        invoices = (
            unpaid.select_related("patient").order_by("-created_at")[:25]
        )

        ctx = {
            "today": today,
            "eyebrow": "Billing",
            "page_title_text": "Billing",
            "subtitle": f"{unpaid_count} unpaid invoice{pluralize(unpaid_count)} · "
                        f"₦{outstanding:,.0f} outstanding.",
            "actions": [
                {"label": "NHIA Claims", "href": reverse("reports:claims"), "icon": "bi-shield-check"},
                {"label": "Billing", "href": reverse("billing:list"), "icon": "bi-cash-stack", "primary": True},
            ],
            "stats": [
                {"label": "Unpaid Invoices", "value": unpaid_count, "tag": "Open", "meta": "issued or partial",
                 "icon": "bi-receipt", "glyph_style": "background:var(--sage-amber-soft);color:var(--sage-amber)"},
                {"label": "Outstanding", "value": f"₦{outstanding:,.0f}", "tag": "Due", "meta": "total balance owed",
                 "icon": "bi-wallet2", "glyph_style": "background:var(--sage-red-soft);color:var(--sage-red)"},
                {"label": "Collected Today", "value": f"₦{paid_today:,.0f}", "tag": "Today", "meta": "payments received",
                 "icon": "bi-cash-coin", "glyph_style": "background:var(--sage-teal-soft);color:var(--sage-teal)"},
                {"label": "Draft Invoices", "value": draft_count, "tag": "Draft", "meta": "not yet issued",
                 "icon": "bi-file-earmark-text", "glyph_style": ""},
            ],
            "panel_template": "core/panels/billing_invoices.html",
            "invoices": invoices,
        }
        return self.role_template_name, ctx

    # ── Front desk (receptionists) ──
    def _reception_context(self, request):
        from patients.models import Patient
        from scheduling.models import Appointment, QueueEntry
        today = date.today()

        appts = Appointment.objects.filter(date=today)
        appts_total = appts.count()
        checked_in = appts.filter(status="checked_in").count()
        queue_waiting = QueueEntry.objects.filter(
            date=today, status=QueueEntry.QueueStatus.WAITING
        ).count()
        registered_today = Patient.objects.filter(created_at__date=today).count()

        appointments_today = (
            appts.filter(status__in=["scheduled", "checked_in"])
            .select_related("patient", "clinic", "consultant")
            .order_by("slot_time")[:25]
        )

        ctx = {
            "today": today,
            "eyebrow": "Front Desk",
            "page_title_text": "Front Desk",
            "subtitle": f"{appts_total} appointment{pluralize(appts_total)} today · "
                        f"{queue_waiting} waiting in the queue.",
            "actions": [
                {"label": "Register Patient", "href": reverse("patients:register"), "icon": "bi-person-plus"},
                {"label": "Walk-in", "href": reverse("scheduling:walkin"), "icon": "bi-box-arrow-in-right"},
                {"label": "Appointments", "href": reverse("scheduling:appointments"), "icon": "bi-calendar3", "primary": True},
            ],
            "stats": [
                {"label": "Appointments Today", "value": appts_total, "tag": "Today", "meta": "booked visits",
                 "icon": "bi-calendar3", "glyph_style": ""},
                {"label": "Checked In", "value": checked_in, "tag": "Live", "meta": "arrived for appointment",
                 "icon": "bi-person-check", "glyph_style": "background:var(--sage-teal-soft);color:var(--sage-teal)"},
                {"label": "Queue Waiting", "value": queue_waiting, "tag": "Live", "meta": "waiting to be seen",
                 "icon": "bi-clock-history", "glyph_style": "background:var(--sage-amber-soft);color:var(--sage-amber)"},
                {"label": "Registered Today", "value": registered_today, "tag": "Today", "meta": "new patients",
                 "icon": "bi-person-plus", "glyph_style": "background:var(--sage-teal-soft);color:var(--sage-teal)"},
            ],
            "panel_template": "core/panels/reception_today.html",
            "appointments_today": appointments_today,
        }
        return self.role_template_name, ctx

    # ── Records (records officers) ──
    def _records_context(self, request):
        from datetime import timedelta
        from patients.models import Patient
        today = date.today()

        total_active = Patient.objects.filter(is_active=True).count()
        registered_today = Patient.objects.filter(created_at__date=today).count()
        registered_week = Patient.objects.filter(
            created_at__date__gte=today - timedelta(days=7)
        ).count()
        inactive = Patient.objects.filter(is_active=False).count()

        recent_patients = (
            Patient.objects.filter(is_active=True)
            .order_by("-created_at")[:25]
        )

        ctx = {
            "today": today,
            "eyebrow": "Health Records",
            "page_title_text": "Health Records",
            "subtitle": f"{registered_today} patient{pluralize(registered_today)} registered today · "
                        f"{total_active} active record{pluralize(total_active)}.",
            "actions": [
                {"label": "Patients", "href": reverse("patients:search"), "icon": "bi-people"},
                {"label": "Register Patient", "href": reverse("patients:register"), "icon": "bi-person-plus", "primary": True},
            ],
            "stats": [
                {"label": "Active Patients", "value": total_active, "tag": "Total", "meta": "active records",
                 "icon": "bi-people", "glyph_style": ""},
                {"label": "Registered Today", "value": registered_today, "tag": "Today", "meta": "new this day",
                 "icon": "bi-person-plus", "glyph_style": "background:var(--sage-teal-soft);color:var(--sage-teal)"},
                {"label": "This Week", "value": registered_week, "tag": "7 days", "meta": "new registrations",
                 "icon": "bi-calendar-week", "glyph_style": "background:var(--sage-amber-soft);color:var(--sage-amber)"},
                {"label": "Inactive", "value": inactive, "tag": "Archived", "meta": "deactivated records",
                 "icon": "bi-archive", "glyph_style": "background:var(--sage-red-soft);color:var(--sage-red)"},
            ],
            "panel_template": "core/panels/records_recent.html",
            "recent_patients": recent_patients,
        }
        return self.role_template_name, ctx
