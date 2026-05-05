from datetime import date, timedelta

import pytest
from django.utils import timezone


TODAY = timezone.localdate()


@pytest.fixture
def doctor(db):
    from accounts.models import User
    return User.objects.create_user(
        email="clm@test.ng", password="x", first_name="C", last_name="L"
    )


@pytest.fixture
def nhia_payer(db):
    from integrations.models import Payer
    return Payer.objects.create(name="NHIA", payer_type="nhia", code="NHIA001")


@pytest.fixture
def nhia_patient(db):
    from patients.models import Patient
    return Patient.objects.create(
        hospital_number="SAGE/2026/CLM001",
        first_name="Amina", last_name="Garba",
        date_of_birth=date(1975, 6, 1), sex="F",
        phone="+2348011223344", payer_type="nhia",
    )


@pytest.fixture
def paid_nhia_invoice(db, nhia_patient, doctor):
    from billing.models import Invoice, InvoiceItem
    from encounters.models import Encounter
    from prescriptions.services import generate_invoice_number
    enc = Encounter.objects.create(
        patient=nhia_patient, attending=doctor, date_time=timezone.now()
    )
    inv = Invoice.objects.create(
        patient=nhia_patient, encounter=enc,
        invoice_number=generate_invoice_number(),
        status=Invoice.Status.PAID,
        subtotal=3000, total=3000, amount_paid=3000, balance=0,
    )
    InvoiceItem.objects.create(
        invoice=inv, description="Consultation", quantity=1,
        unit_price=3000, total=3000,
    )
    return inv


# ── build_claim_batch ─────────────────────────────────────────

@pytest.mark.django_db
def test_build_batch_includes_nhia_invoices(nhia_payer, paid_nhia_invoice, doctor):
    from integrations.services import build_claim_batch
    batch, claims = build_claim_batch(
        nhia_payer,
        TODAY - timedelta(days=1),
        TODAY + timedelta(days=1),
        submitted_by=doctor,
    )
    assert len(claims) == 1
    assert claims[0].invoice_id == paid_nhia_invoice.pk
    assert batch.total_claimed == 3000


@pytest.mark.django_db
def test_build_batch_excludes_already_claimed(nhia_payer, paid_nhia_invoice, doctor):
    from integrations.services import build_claim_batch
    period = (TODAY - timedelta(days=1), TODAY + timedelta(days=1))
    build_claim_batch(nhia_payer, *period, submitted_by=doctor)
    _, claims2 = build_claim_batch(nhia_payer, *period, submitted_by=doctor)
    assert len(claims2) == 0


@pytest.mark.django_db
def test_build_batch_excludes_self_pay_patients(nhia_payer, doctor, db):
    from billing.models import Invoice
    from encounters.models import Encounter
    from patients.models import Patient
    from prescriptions.services import generate_invoice_number
    self_pay = Patient.objects.create(
        hospital_number="SAGE/2026/SP001",
        first_name="John", last_name="Doe",
        date_of_birth=date(1980, 1, 1), sex="M",
        phone="+2348011111111", payer_type="self_pay",
    )
    enc = Encounter.objects.create(
        patient=self_pay, attending=doctor, date_time=timezone.now()
    )
    Invoice.objects.create(
        patient=self_pay, encounter=enc,
        invoice_number=generate_invoice_number(),
        status=Invoice.Status.PAID,
        subtotal=2000, total=2000, amount_paid=2000, balance=0,
    )
    from integrations.services import build_claim_batch
    _, claims = build_claim_batch(
        nhia_payer,
        TODAY - timedelta(days=1),
        TODAY + timedelta(days=1),
        submitted_by=doctor,
    )
    assert len(claims) == 0


# ── submit_batch ──────────────────────────────────────────────

@pytest.mark.django_db
def test_submit_batch_changes_status(nhia_payer, paid_nhia_invoice, doctor):
    from integrations.models import ClaimBatch
    from integrations.services import build_claim_batch, submit_batch
    batch, _ = build_claim_batch(
        nhia_payer,
        TODAY - timedelta(days=1),
        TODAY + timedelta(days=1),
        submitted_by=doctor,
    )
    submit_batch(batch, doctor)
    batch.refresh_from_db()
    assert batch.status == ClaimBatch.Status.SUBMITTED
    assert batch.submitted_at is not None


@pytest.mark.django_db
def test_submit_already_submitted_raises(nhia_payer, paid_nhia_invoice, doctor):
    from integrations.services import build_claim_batch, submit_batch
    batch, _ = build_claim_batch(
        nhia_payer,
        TODAY - timedelta(days=1),
        TODAY + timedelta(days=1),
        submitted_by=doctor,
    )
    submit_batch(batch, doctor)
    with pytest.raises(ValueError, match="Only draft batches"):
        submit_batch(batch, doctor)
