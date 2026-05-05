from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View


def _get_alerts(user):
    """Return list of actionable system alerts for the notification bell."""
    alerts = []

    from laboratory.models import LabOrder
    critical_unacked = LabOrder.objects.filter(
        result__is_critical=True,
        result__critical_acknowledged_at__isnull=True,
    ).select_related("patient", "test").order_by("-created_at")[:10]
    for order in critical_unacked:
        alerts.append({
            "type": "critical_lab",
            "level": "red",
            "icon": "bi-exclamation-triangle-fill",
            "title": f"Critical: {order.test.name}",
            "body": order.patient.full_name,
            "url": f"/lab/order/{order.pk}/",
        })

    from admissions.models import Admission
    from django.utils import timezone
    today = timezone.localdate()
    long_stay = Admission.objects.filter(
        status=Admission.Status.ACTIVE,
        admitted_at__date__lte=today,
    ).select_related("patient").order_by("admitted_at")
    long_stay = [a for a in long_stay if (today - a.admitted_at.date()).days >= 14][:5]
    for adm in long_stay:
        days = (today - adm.admitted_at.date()).days
        alerts.append({
            "type": "long_stay",
            "level": "amber",
            "icon": "bi-hospital",
            "title": f"Long stay: Day {days}",
            "body": adm.patient.full_name,
            "url": f"/admissions/{adm.pk}/",
        })

    from prescriptions.models import Prescription
    pending_rx = Prescription.objects.filter(status="pending").count()
    if pending_rx:
        alerts.append({
            "type": "pending_rx",
            "level": "blue",
            "icon": "bi-capsule",
            "title": f"{pending_rx} pending prescription{'s' if pending_rx != 1 else ''}",
            "body": "Awaiting dispensing",
            "url": "/prescriptions/?status=pending",
        })

    return alerts


@method_decorator(login_required, name="dispatch")
class NotificationBellView(View):
    """Returns an HTML fragment for the bell dropdown."""

    def get(self, request):
        alerts = _get_alerts(request.user)
        return render(request, "notifications/_bell_dropdown.html", {
            "alerts": alerts,
        })


@method_decorator(login_required, name="dispatch")
class NotificationCountView(View):
    """Returns JSON {count: N} for badge polling."""

    def get(self, request):
        alerts = _get_alerts(request.user)
        return JsonResponse({"count": len(alerts)})
