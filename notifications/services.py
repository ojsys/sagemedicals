"""
Notification dispatch engine.
All functions are side-effect free in tests (provider calls are skipped when
SMS_API_KEY is blank or email backend is console/locmem).
"""
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone


def _render(template_str, context):
    """Simple {{ key }} substitution — no Jinja, no template engine overhead."""
    result = template_str
    for key, value in context.items():
        result = result.replace(f"{{{{{key}}}}}", str(value))
    return result


def send_sms(phone, body, patient=None, event_type=""):
    """
    Send an SMS via the configured provider (Termii by default).
    Falls back silently when SMS_API_KEY is not set (local dev).
    Returns a Notification instance.
    """
    from notifications.models import Notification

    notif = Notification.objects.create(
        patient=patient,
        channel=Notification.Channel.SMS,
        recipient=phone,
        body=body,
        event_type=event_type,
    )

    api_key = getattr(settings, "SMS_API_KEY", "")
    if not api_key:
        notif.status = Notification.Status.SENT
        notif.sent_at = timezone.now()
        notif.provider_reference = "dev-skip"
        notif.save(update_fields=["status", "sent_at", "provider_reference"])
        return notif

    try:
        import urllib.request, json as _json
        payload = _json.dumps({
            "to": phone,
            "from": getattr(settings, "SMS_SENDER_ID", "SAGE"),
            "sms": body,
            "type": "plain",
            "channel": "generic",
            "api_key": api_key,
        }).encode()
        req = urllib.request.Request(
            "https://api.ng.termii.com/api/sms/send",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read())
            notif.provider_reference = str(data.get("message_id", ""))
            notif.status = Notification.Status.SENT
    except Exception as exc:
        notif.status = Notification.Status.FAILED
        notif.error_message = str(exc)

    notif.sent_at = timezone.now()
    notif.save(update_fields=["status", "sent_at", "provider_reference", "error_message"])
    return notif


def send_email_notification(to_email, subject, body, patient=None, event_type=""):
    """
    Send a plain-text email. Uses Django's configured email backend.
    Returns a Notification instance.
    """
    from notifications.models import Notification

    notif = Notification.objects.create(
        patient=patient,
        channel=Notification.Channel.EMAIL,
        recipient=to_email,
        subject=subject,
        body=body,
        event_type=event_type,
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            fail_silently=False,
        )
        notif.status = Notification.Status.SENT
    except Exception as exc:
        notif.status = Notification.Status.FAILED
        notif.error_message = str(exc)

    notif.sent_at = timezone.now()
    notif.save(update_fields=["status", "sent_at", "error_message"])
    return notif


def send_from_template(event_type, context, patient=None):
    """
    Render and dispatch using a NotificationTemplate.
    Silently skips if no active template exists for the event.
    Returns list of Notification instances dispatched.
    """
    from notifications.models import NotificationTemplate

    try:
        tmpl = NotificationTemplate.objects.get(event_type=event_type, is_active=True)
    except NotificationTemplate.DoesNotExist:
        return []

    sent = []
    if tmpl.channel in (NotificationTemplate.Channel.SMS, NotificationTemplate.Channel.BOTH):
        phone = context.get("phone") or (patient.phone if patient else None)
        if phone and tmpl.body_sms:
            body = _render(tmpl.body_sms, context)
            sent.append(send_sms(phone, body, patient=patient, event_type=event_type))

    if tmpl.channel in (NotificationTemplate.Channel.EMAIL, NotificationTemplate.Channel.BOTH):
        email = context.get("email") or (patient.email if hasattr(patient, "email") else None)
        if email and tmpl.body_email:
            body = _render(tmpl.body_email, context)
            subject = _render(tmpl.subject, context)
            sent.append(
                send_email_notification(email, subject, body, patient=patient, event_type=event_type)
            )
    return sent


# ── OTP ───────────────────────────────────────────────────────

MAX_OTP_ATTEMPTS = 5
OTP_TTL_MINUTES = 10


def issue_otp(phone):
    """
    Generate and dispatch a 6-digit OTP to the given phone number.
    Invalidates any prior unused OTPs for the same phone.
    Returns the OTPVerification instance.
    """
    from notifications.models import OTPVerification

    OTPVerification.objects.filter(phone=phone, is_used=False).update(is_used=True)

    code = f"{secrets.randbelow(1_000_000):06d}"
    otp = OTPVerification.objects.create(
        phone=phone,
        code=code,
        expires_at=timezone.now() + timedelta(minutes=OTP_TTL_MINUTES),
    )
    body = f"Your SAGE Medical OTP is {code}. Valid for {OTP_TTL_MINUTES} minutes. Do not share."
    send_sms(phone, body, event_type="otp_verify")
    return otp


def verify_otp(phone, code):
    """
    Verify an OTP. Returns True on success, False otherwise.
    Increments attempt counter; marks used on success.
    """
    from notifications.models import OTPVerification

    otp = (
        OTPVerification.objects.filter(phone=phone, is_used=False)
        .order_by("-created_at")
        .first()
    )
    if not otp:
        return False
    if otp.expires_at < timezone.now():
        return False
    if otp.attempts >= MAX_OTP_ATTEMPTS:
        return False

    otp.attempts += 1
    if otp.code != code:
        otp.save(update_fields=["attempts"])
        return False

    otp.is_used = True
    otp.save(update_fields=["is_used", "attempts"])
    return True


def notify_appointment(appointment):
    """Fire appointment-booked notification for a patient."""
    patient = appointment.patient
    context = {
        "patient_name": patient.full_name,
        "date": str(appointment.date),
        "time": appointment.slot_time.strftime("%H:%M"),
        "clinic": str(appointment.clinic),
        "phone": patient.phone,
    }
    send_from_template(
        "appointment_booked", context, patient=patient
    )


def notify_lab_result(lab_order):
    """Fire lab-result-ready notification."""
    patient = lab_order.patient
    context = {
        "patient_name": patient.full_name,
        "test_name": lab_order.test.name,
        "phone": patient.phone,
    }
    send_from_template("lab_result_ready", context, patient=patient)


def notify_invoice(invoice):
    """Fire invoice-issued notification."""
    patient = invoice.patient
    context = {
        "patient_name": patient.full_name,
        "invoice_number": invoice.invoice_number,
        "total": str(invoice.total),
        "phone": patient.phone,
    }
    send_from_template("invoice_issued", context, patient=patient)
