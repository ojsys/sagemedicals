from datetime import timedelta

from django.conf import settings
from django.db import transaction, IntegrityError
from django.utils import timezone

PORTAL_SESSION_COOKIE = "portal_token"





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


from accounts.models import User
from patients.models import Patient
from patients.services import generate_hospital_number

def self_register(first_name, last_name, date_of_birth, sex, email, password, phone=""):
    """
    Register a new patient via the portal.
    Creates a User account and a Patient profile linked to it.
    Returns (patient, created).
    """
    # Check if a User with this email already exists
    if User.objects.filter(email=email).exists():
        raise ValueError("A user with this email already exists.")

    # Check if a Patient with this email already exists (even without a linked user)
    existing_patient = Patient.objects.filter(email=email, deleted_at__isnull=True).first()
    if existing_patient:
        raise ValueError("A patient with this email already exists.")

    # Create the User account first
    user = User.objects.create_user(email=email, password=password, first_name=first_name, last_name=last_name)
    user.save() # Save the user to ensure first_name and last_name are set

    MAX_RETRIES = 5
    for _ in range(MAX_RETRIES):
        try:
            with transaction.atomic():  # New atomic block for each retry attempt
                hospital_number = generate_hospital_number()
                patient = Patient.objects.create(
                    hospital_number=hospital_number,
                    first_name=first_name.strip().title(),
                    last_name=last_name.strip().title(),
                    date_of_birth=date_of_birth,
                    sex=sex,
                    email=email,  # Set patient email from registration
                    phone=phone,  # Phone is now optional
                    user=user,  # Link the created User object
                    payer_type="self_pay",
                )
                return patient, True
        except IntegrityError as e:
            if "hospital_number" in str(e):
                continue
            else:
                # If it's another IntegrityError (e.g., email unique constraint for Patient model),
                # we should re-raise, as it indicates a serious data consistency issue
                # or a race condition not related to hospital_number generation.
                raise
    raise IntegrityError("Failed to create patient after multiple retries due to duplicate hospital number.")
