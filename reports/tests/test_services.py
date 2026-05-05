from datetime import date, timedelta

import pytest
from django.utils import timezone


TODAY = timezone.localdate()


@pytest.fixture
def doctor(db):
    from accounts.models import User
    return User.objects.create_user(
        email="rpt@test.ng", password="x", first_name="R", last_name="P"
    )


@pytest.fixture
def cashier(db):
    from accounts.models import User
    return User.objects.create_user(
        email="cash@test.ng", password="x", first_name="C", last_name="A"
    )


@pytest.fixture
def patient(db):
    from patients.models import Patient
    return Patient.objects.create(
        hospital_number="SAGE/2026/RPT001",
        first_name="Chidi", last_name="Obi",
        date_of_birth=date(1990, 1, 1), sex="M",
        phone="+2348099111111", payer_type="self_pay",
    )


@pytest.fixture
def encounter(db, patient, doctor):
    from encounters.models import Encounter
    return Encounter.objects.create(
        patient=patient, attending=doctor, date_time=timezone.now()
    )


@pytest.fixture
def paid_invoice(db, patient, encounter, cashier):
    from billing.models import Invoice, InvoiceItem, Payment
    from prescriptions.services import generate_invoice_number
    inv = Invoice.objects.create(
        patient=patient, encounter=encounter,
        invoice_number=generate_invoice_number(),
        status=Invoice.Status.PAID,
        subtotal=5000, total=5000, amount_paid=5000, balance=0,
    )
    InvoiceItem.objects.create(
        invoice=inv, description="Consultation", quantity=1,
        unit_price=5000, total=5000,
    )
    Payment.objects.create(
        invoice=inv, amount=5000, mode="cash",
        reference="", cashier=cashier,
    )
    return inv


# ── revenue_summary ───────────────────────────────────────────

@pytest.mark.django_db
def test_revenue_summary_counts_payments(paid_invoice):
    from reports.services import revenue_summary
    result = revenue_summary(TODAY - timedelta(days=1), TODAY + timedelta(days=1))
    assert result["total"] == 5000


@pytest.mark.django_db
def test_revenue_summary_outside_range_excluded(paid_invoice):
    from reports.services import revenue_summary
    yesterday = TODAY - timedelta(days=5)
    result = revenue_summary(yesterday - timedelta(days=2), yesterday)
    assert result["total"] == 0


# ── daily_snapshot ────────────────────────────────────────────

@pytest.mark.django_db
def test_daily_snapshot_outpatients(encounter):
    from reports.services import daily_snapshot
    snap = daily_snapshot(TODAY)
    assert snap["outpatients"] >= 1


@pytest.mark.django_db
def test_daily_snapshot_revenue(paid_invoice):
    from reports.services import daily_snapshot
    snap = daily_snapshot(TODAY)
    assert snap["revenue_today"] >= 5000


# ── top_diagnoses ─────────────────────────────────────────────

@pytest.mark.django_db
def test_top_diagnoses_returns_results(encounter):
    from encounters.models import Diagnosis
    from reports.services import top_diagnoses
    Diagnosis.objects.create(
        encounter=encounter, icd10_code="A09", description="Diarrhoea",
        diagnosis_type="primary", clinician=encounter.attending,
    )
    result = list(top_diagnoses(TODAY - timedelta(days=1), TODAY + timedelta(days=1)))
    codes = [d["icd10_code"] for d in result]
    assert "A09" in codes


# ── monthly_return ────────────────────────────────────────────

@pytest.mark.django_db
def test_monthly_return_structure(encounter):
    from reports.services import monthly_return
    data = monthly_return(TODAY.year, TODAY.month)
    assert "new_registrations" in data
    assert "total_outpatient_visits" in data
    assert "revenue" in data
    assert data["total_outpatient_visits"] >= 0


# ── bed_occupancy ─────────────────────────────────────────────

@pytest.mark.django_db
def test_bed_occupancy_totals(db):
    from admissions.models import Bed, Room, Ward
    from reports.services import bed_occupancy
    ward = Ward.objects.create(name="Test Ward")
    room = Room.objects.create(ward=ward, name="R1")
    Bed.objects.create(room=room, label="1", status=Bed.Status.AVAILABLE)
    Bed.objects.create(room=room, label="2", status=Bed.Status.OCCUPIED)
    occ = bed_occupancy(ward)
    assert occ["total"] == 2
    assert occ["occupied"] == 1
    assert occ["available"] == 1
    assert occ["occupancy_pct"] == 50.0
