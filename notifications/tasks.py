"""
django-q2 task functions for async notification dispatch.

Queue a task:
    from django_q.tasks import async_task
    async_task('notifications.tasks.send_appointment_reminder_task', appointment_pk)

In production these run via: python manage.py qcluster
In local dev Q_CLUSTER sync=True means they run inline.
"""
import logging

logger = logging.getLogger("sage")


def send_appointment_reminder_task(appointment_pk):
    """Async: send appointment reminder for a single appointment."""
    from scheduling.models import Appointment
    from notifications.services import send_from_template

    try:
        appt = Appointment.objects.select_related("patient", "clinic").get(pk=appointment_pk)
    except Appointment.DoesNotExist:
        logger.warning("send_appointment_reminder_task: appointment %s not found", appointment_pk)
        return

    patient = appt.patient
    send_from_template(
        "appointment_reminder",
        {
            "patient_name": patient.full_name,
            "date": str(appt.date),
            "time": appt.slot_time.strftime("%H:%M"),
            "clinic": str(appt.clinic),
            "phone": patient.phone,
        },
        patient=patient,
    )
    logger.info("Reminder dispatched for appointment %s", appointment_pk)


def send_lab_result_notification_task(lab_order_pk):
    """Async: notify patient that a lab result is released."""
    from laboratory.models import LabOrder
    from notifications.services import notify_lab_result

    try:
        order = LabOrder.objects.select_related("patient", "test").get(pk=lab_order_pk)
    except LabOrder.DoesNotExist:
        logger.warning("send_lab_result_notification_task: order %s not found", lab_order_pk)
        return

    notify_lab_result(order)
    logger.info("Lab result notification dispatched for order %s", lab_order_pk)


def send_invoice_notification_task(invoice_pk):
    """Async: notify patient of a newly issued invoice."""
    from billing.models import Invoice
    from notifications.services import notify_invoice

    try:
        invoice = Invoice.objects.select_related("patient").get(pk=invoice_pk)
    except Invoice.DoesNotExist:
        logger.warning("send_invoice_notification_task: invoice %s not found", invoice_pk)
        return

    notify_invoice(invoice)
    logger.info("Invoice notification dispatched for invoice %s", invoice_pk)


def expire_portal_sessions_task():
    """Async: clean up expired portal sessions (run nightly)."""
    from django.utils import timezone
    from portal.models import PortalSession

    deleted, _ = PortalSession.objects.filter(expires_at__lt=timezone.now()).delete()
    logger.info("Expired %d portal sessions", deleted)
    return deleted
