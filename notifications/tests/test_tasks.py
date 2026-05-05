from datetime import date, timedelta

import pytest
from django.utils import timezone


@pytest.fixture
def doctor(db):
    from accounts.models import User
    return User.objects.create_user(
        email="task_doc@test.ng", password="x", first_name="T", last_name="D"
    )


@pytest.fixture
def patient(db):
    from patients.models import Patient
    return Patient.objects.create(
        hospital_number="SAGE/2026/TSK001",
        first_name="Bukola", last_name="Adeyemi",
        date_of_birth=date(1990, 1, 1), sex="F",
        phone="+2348077000001", payer_type="self_pay",
    )


@pytest.mark.django_db
def test_expire_portal_sessions_task(patient):
    from portal.models import PortalSession
    from notifications.tasks import expire_portal_sessions_task

    PortalSession.objects.create(
        patient=patient,
        expires_at=timezone.now() - timedelta(hours=1),
    )
    PortalSession.objects.create(
        patient=patient,
        expires_at=timezone.now() + timedelta(hours=1),
    )
    deleted = expire_portal_sessions_task()
    assert deleted == 1
    assert PortalSession.objects.count() == 1


@pytest.mark.django_db
def test_send_lab_result_notification_task_missing_order():
    from notifications.tasks import send_lab_result_notification_task
    # Should not raise — just logs a warning
    send_lab_result_notification_task(99999)


@pytest.mark.django_db
def test_send_invoice_notification_task_missing_invoice():
    from notifications.tasks import send_invoice_notification_task
    send_invoice_notification_task(99999)
