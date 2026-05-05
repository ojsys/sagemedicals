import json
import time
from datetime import date

from django.contrib.auth.decorators import login_required
from django.db import connection
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


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


@method_decorator(login_required, name="dispatch")
class TutorialView(View):
    template_name = "core/tutorial.html"

    def get(self, request):
        return render(request, self.template_name)


@method_decorator(login_required, name="dispatch")
class DashboardView(View):
    template_name = "core/dashboard.html"

    def get(self, request):
        today = date.today()

        from admissions.models import Admission
        from laboratory.models import LabOrder
        from patients.models import Patient
        from scheduling.models import Appointment, QueueEntry

        patients_today = Patient.objects.filter(
            created_at__date=today, is_active=True
        ).count()

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

        return render(request, self.template_name, {
            "today": today,
            "patients_today": patients_today,
            "active_admissions": active_admissions,
            "queue_waiting": queue_waiting,
            "pending_labs": pending_labs,
            "queue_today": queue_today,
            "appointments_today": appointments_today,
            "recent_patients": recent_patients,
            "recent_admissions": recent_admissions,
        })
