from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

PORTAL_SESSION_COOKIE = "portal_token"


def start_otp_login(phone):
    """Normalise phone, find or hint at patient, issue OTP. Returns phone."""
    from notifications.services import issue_otp
    from patients.services import normalise_phone, validate_nigerian_phone

    phone = normalise_phone(phone)
    validate_nigerian_phone(phone)
    issue_otp(phone)
    return phone


@transaction.atomic
def complete_otp_login(phone, code, ip=None, ua=""):
    """
    Verify OTP and return a PortalSession.
    Raises ValueError if OTP is wrong/expired or no patient matches phone.
    """
    from notifications.services import verify_otp
    from patients.models import Patient
    from portal.models import PortalSession

    if not verify_otp(phone, code):
        raise ValueError("Invalid or expired verification code.")

    patient = Patient.objects.filter(phone=phone, deleted_at__isnull=True).first()
    if not patient:
        raise ValueError("No patient account found for this phone number.")

    ttl = getattr(settings, "PATIENT_PORTAL_SESSION_AGE", 3600)
    session = PortalSession.objects.create(
        patient=patient,
        expires_at=timezone.now() + timedelta(seconds=ttl),
        ip_address=ip,
        user_agent=ua,
    )
    return session


def get_portal_session(request):
    """
    Retrieve and validate the portal session from the cookie.
    Returns PortalSession or None.
    """
    from portal.models import PortalSession

    token = request.COOKIES.get(PORTAL_SESSION_COOKIE)
    if not token:
        return None
    session = PortalSession.objects.filter(token=token).select_related("patient").first()
    if not session or not session.is_valid:
        return None
    session.touch()
    return session


def portal_login_required(view_func):
    """Decorator for portal views — redirects to portal login if no valid session."""
    from functools import wraps

    from django.shortcuts import redirect

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        session = get_portal_session(request)
        if not session:
            return redirect("portal:login")
        request.portal_session = session
        request.portal_patient = session.patient
        return view_func(request, *args, **kwargs)

    return wrapper


@transaction.atomic
def self_register(first_name, last_name, date_of_birth, sex, phone, email=""):
    """
    Register a new patient via the portal (OTP already verified).
    Returns (patient, created).
    """
    from patients.models import Patient
    from patients.services import generate_hospital_number, normalise_phone

    phone = normalise_phone(phone)
    existing = Patient.objects.filter(phone=phone, deleted_at__isnull=True).first()
    if existing:
        return existing, False

    hospital_number = generate_hospital_number()
    patient = Patient.objects.create(
        hospital_number=hospital_number,
        first_name=first_name.strip().title(),
        last_name=last_name.strip().title(),
        date_of_birth=date_of_birth,
        sex=sex,
        phone=phone,
        payer_type="self_pay",
    )
    return patient, True
