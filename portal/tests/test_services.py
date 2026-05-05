from datetime import date, timedelta

import pytest
from django.utils import timezone


@pytest.fixture
def patient(db):
    from patients.models import Patient
    return Patient.objects.create(
        hospital_number="SAGE/2026/PRT001",
        first_name="Emeka", last_name="Okafor",
        date_of_birth=date(1988, 7, 15), sex="M",
        phone="+2348077889900", payer_type="self_pay",
    )


# ── OTP login flow ────────────────────────────────────────────

@pytest.mark.django_db
def test_complete_otp_login_creates_session(patient):
    from notifications.services import issue_otp
    from portal.services import complete_otp_login
    otp = issue_otp(patient.phone)
    session = complete_otp_login(patient.phone, otp.code)
    assert session.patient_id == patient.pk
    assert session.is_valid
    assert len(session.token) >= 32


@pytest.mark.django_db
def test_complete_otp_login_wrong_code_raises(patient):
    from notifications.services import issue_otp
    from portal.services import complete_otp_login
    issue_otp(patient.phone)
    with pytest.raises(ValueError, match="Invalid or expired"):
        complete_otp_login(patient.phone, "000000")


@pytest.mark.django_db
def test_complete_otp_login_no_patient_raises():
    from notifications.services import issue_otp
    from portal.services import complete_otp_login
    phone = "+2348099000111"
    otp = issue_otp(phone)
    with pytest.raises(ValueError, match="No patient account"):
        complete_otp_login(phone, otp.code)


# ── self_register ─────────────────────────────────────────────

@pytest.mark.django_db
def test_self_register_creates_patient():
    from portal.services import self_register
    patient, created = self_register(
        first_name="Kemi",
        last_name="Adeleke",
        date_of_birth=date(1995, 3, 10),
        sex="F",
        phone="+2348012000001",
    )
    assert created is True
    assert patient.first_name == "Kemi"
    assert patient.hospital_number.startswith("SAGE/")


@pytest.mark.django_db
def test_self_register_existing_returns_false(patient):
    from portal.services import self_register
    existing, created = self_register(
        first_name="Other",
        last_name="Name",
        date_of_birth=date(1990, 1, 1),
        sex="M",
        phone=patient.phone,
    )
    assert created is False
    assert existing.pk == patient.pk


# ── PortalSession validity ────────────────────────────────────

@pytest.mark.django_db
def test_portal_session_valid(patient):
    from portal.models import PortalSession
    session = PortalSession.objects.create(
        patient=patient,
        expires_at=timezone.now() + timedelta(hours=1),
    )
    assert session.is_valid is True


@pytest.mark.django_db
def test_portal_session_expired(patient):
    from portal.models import PortalSession
    session = PortalSession.objects.create(
        patient=patient,
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    assert session.is_valid is False
