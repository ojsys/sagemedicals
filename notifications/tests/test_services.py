from datetime import date
from datetime import timedelta

import pytest
from django.utils import timezone


@pytest.fixture
def patient(db):
    from patients.models import Patient
    return Patient.objects.create(
        hospital_number="SAGE/2026/NTF001",
        first_name="Ngozi", last_name="Eze",
        date_of_birth=date(1992, 4, 1), sex="F",
        phone="+2348055667788", payer_type="self_pay",
    )


# ── OTP ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_issue_otp_creates_record():
    from notifications.services import issue_otp
    otp = issue_otp("+2348055667788")
    assert len(otp.code) == 6
    assert not otp.is_used
    assert otp.expires_at > timezone.now()


@pytest.mark.django_db
def test_verify_otp_correct_code():
    from notifications.services import issue_otp, verify_otp
    otp = issue_otp("+2348011223344")
    assert verify_otp("+2348011223344", otp.code) is True
    otp.refresh_from_db()
    assert otp.is_used is True


@pytest.mark.django_db
def test_verify_otp_wrong_code():
    from notifications.services import issue_otp, verify_otp
    issue_otp("+2348011223344")
    assert verify_otp("+2348011223344", "000000") is False


@pytest.mark.django_db
def test_verify_otp_expired():
    from notifications.models import OTPVerification
    from notifications.services import verify_otp
    otp = OTPVerification.objects.create(
        phone="+2348099999999",
        code="123456",
        expires_at=timezone.now() - timedelta(minutes=1),
    )
    assert verify_otp("+2348099999999", "123456") is False


@pytest.mark.django_db
def test_issue_otp_invalidates_previous():
    from notifications.models import OTPVerification
    from notifications.services import issue_otp
    first = issue_otp("+2348055667788")
    issue_otp("+2348055667788")
    first.refresh_from_db()
    assert first.is_used is True


@pytest.mark.django_db
def test_verify_otp_max_attempts():
    from notifications.models import OTPVerification
    from notifications.services import verify_otp
    otp = OTPVerification.objects.create(
        phone="+2348011111111",
        code="654321",
        expires_at=timezone.now() + timedelta(minutes=10),
        attempts=5,
    )
    assert verify_otp("+2348011111111", "654321") is False


# ── send_sms (dev mode — no real API key) ────────────────────

@pytest.mark.django_db
def test_send_sms_creates_notification(patient):
    from notifications.models import Notification
    from notifications.services import send_sms
    notif = send_sms(patient.phone, "Test message", patient=patient)
    assert notif.pk is not None
    assert notif.status == Notification.Status.SENT
    assert notif.provider_reference == "dev-skip"


# ── send_from_template ────────────────────────────────────────

@pytest.mark.django_db
def test_send_from_template_no_template_is_silent(patient):
    from notifications.services import send_from_template
    result = send_from_template("appointment_booked", {}, patient=patient)
    assert result == []


@pytest.mark.django_db
def test_send_from_template_dispatches(patient):
    from notifications.models import Notification, NotificationTemplate
    from notifications.services import send_from_template
    NotificationTemplate.objects.create(
        event_type="appointment_booked",
        channel=NotificationTemplate.Channel.SMS,
        body_sms="Hi {{patient_name}}, your appt is confirmed.",
        is_active=True,
    )
    result = send_from_template(
        "appointment_booked",
        {"patient_name": patient.full_name, "phone": patient.phone},
        patient=patient,
    )
    assert len(result) == 1
    assert "Ngozi" in result[0].body
