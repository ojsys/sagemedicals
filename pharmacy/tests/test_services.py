from datetime import date, timedelta

import pytest
from django.utils import timezone


@pytest.fixture
def store(db):
    from pharmacy.models import Store
    return Store.objects.create(name="Main Pharmacy", is_main=True)


@pytest.fixture
def drug(db):
    from prescriptions.models import Drug
    return Drug.objects.create(
        generic_name="Paracetamol", strength="500mg",
        dosage_form="tablet", category="otc", is_formulary=True,
    )


@pytest.fixture
def patient(db):
    from patients.models import Patient
    return Patient.objects.create(
        hospital_number="SAGE/2026/000001",
        first_name="Ade", last_name="Obi",
        date_of_birth=date(1990, 1, 1), sex="F",
        phone="+2348012345678", payer_type="self_pay",
    )


@pytest.fixture
def doctor(db):
    from accounts.models import User
    return User.objects.create_user(email="pharm@test.ng", password="x", first_name="P", last_name="H")


@pytest.fixture
def encounter(db, patient, doctor):
    from encounters.models import Encounter
    return Encounter.objects.create(patient=patient, attending=doctor, date_time=timezone.now())


@pytest.fixture
def batch(db, drug, store):
    from pharmacy.models import DrugBatch
    return DrugBatch.objects.create(
        drug=drug, store=store, batch_number="B001",
        expiry_date=date.today() + timedelta(days=180),
        quantity_received=100, quantity_remaining=100,
        unit_cost="5.00",
    )


# ── FEFO tests ────────────────────────────────────────────────

@pytest.mark.django_db
def test_fefo_single_batch(drug, store, batch):
    from pharmacy.services import get_fefo_batches
    plan = get_fefo_batches(drug, store, 10)
    assert len(plan) == 1
    assert plan[0][0].pk == batch.pk
    assert plan[0][1] == 10


@pytest.mark.django_db
def test_fefo_splits_across_batches(drug, store):
    from pharmacy.models import DrugBatch
    from pharmacy.services import get_fefo_batches
    b1 = DrugBatch.objects.create(
        drug=drug, store=store, batch_number="EARLY",
        expiry_date=date.today() + timedelta(days=30),
        quantity_received=8, quantity_remaining=8, unit_cost="5.00",
    )
    b2 = DrugBatch.objects.create(
        drug=drug, store=store, batch_number="LATER",
        expiry_date=date.today() + timedelta(days=200),
        quantity_received=50, quantity_remaining=50, unit_cost="5.00",
    )
    plan = get_fefo_batches(drug, store, 20)
    assert plan[0][0].pk == b1.pk
    assert plan[0][1] == 8
    assert plan[1][0].pk == b2.pk
    assert plan[1][1] == 12


@pytest.mark.django_db
def test_fefo_insufficient_stock_raises(drug, store, batch):
    from pharmacy.services import get_fefo_batches
    with pytest.raises(ValueError, match="Insufficient stock"):
        get_fefo_batches(drug, store, 999)


@pytest.mark.django_db
def test_fefo_skips_expired(drug, store):
    from pharmacy.models import DrugBatch
    from pharmacy.services import get_fefo_batches
    DrugBatch.objects.create(
        drug=drug, store=store, batch_number="EXPIRED",
        expiry_date=date.today() - timedelta(days=1),
        quantity_received=50, quantity_remaining=50, unit_cost="5.00",
    )
    with pytest.raises(ValueError):
        get_fefo_batches(drug, store, 1)


@pytest.mark.django_db
def test_fefo_skips_quarantined(drug, store):
    from pharmacy.models import DrugBatch
    from pharmacy.services import get_fefo_batches
    DrugBatch.objects.create(
        drug=drug, store=store, batch_number="QUAR",
        expiry_date=date.today() + timedelta(days=90),
        quantity_received=50, quantity_remaining=50, unit_cost="5.00",
        is_quarantined=True,
    )
    with pytest.raises(ValueError):
        get_fefo_batches(drug, store, 1)


# ── Dispense tests ────────────────────────────────────────────

@pytest.mark.django_db
def test_dispense_reduces_batch_quantity(drug, store, batch, patient, doctor, encounter):
    from prescriptions.models import Prescription
    from pharmacy.services import dispense_prescription

    rx = Prescription.objects.create(
        drug=drug, patient=patient, encounter=encounter,
        prescriber=doctor, dose="500mg", quantity=10, status="pending",
    )
    dispense_prescription(rx, store, doctor)
    batch.refresh_from_db()
    assert batch.quantity_remaining == 90


@pytest.mark.django_db
def test_dispense_updates_prescription_status(drug, store, batch, patient, doctor, encounter):
    from prescriptions.models import Prescription
    from pharmacy.services import dispense_prescription

    rx = Prescription.objects.create(
        drug=drug, patient=patient, encounter=encounter,
        prescriber=doctor, dose="500mg", quantity=5, status="pending",
    )
    dispense_prescription(rx, store, doctor)
    rx.refresh_from_db()
    assert rx.status == "dispensed"


@pytest.mark.django_db
def test_dispense_cannot_be_repeated(drug, store, batch, patient, doctor, encounter):
    from prescriptions.models import Prescription
    from pharmacy.services import dispense_prescription

    rx = Prescription.objects.create(
        drug=drug, patient=patient, encounter=encounter,
        prescriber=doctor, dose="500mg", quantity=5, status="pending",
    )
    dispense_prescription(rx, store, doctor)
    rx.status = "pending"
    rx.save()
    with pytest.raises(ValueError, match="already dispensed"):
        dispense_prescription(rx, store, doctor)


# ── Goods receipt tests ───────────────────────────────────────

@pytest.mark.django_db
def test_receive_goods_creates_batch_and_stock(drug, store, doctor):
    from pharmacy.models import GoodsReceipt, GoodsReceiptLine, StockLevel
    from pharmacy.services import receive_goods

    receipt = GoodsReceipt.objects.create(
        store=store, supplier="MedCo", received_date=date.today(),
        received_by=doctor,
    )
    GoodsReceiptLine.objects.create(
        receipt=receipt, drug=drug, batch_number="NEWBATCH",
        expiry_date=date.today() + timedelta(days=365),
        quantity_ordered=100, quantity_received=100, unit_cost="4.50",
    )
    receive_goods(receipt)
    sl = StockLevel.objects.get(drug=drug, store=store)
    assert sl.quantity_on_hand == 100


@pytest.mark.django_db
def test_expiry_alerts_returns_near_expiry(drug, store):
    from pharmacy.models import DrugBatch
    from pharmacy.services import get_expiry_alerts

    DrugBatch.objects.create(
        drug=drug, store=store, batch_number="NEAR",
        expiry_date=date.today() + timedelta(days=30),
        quantity_received=10, quantity_remaining=10, unit_cost="5.00",
    )
    alerts = get_expiry_alerts(store, days_ahead=90)
    assert any(b.batch_number == "NEAR" for b in alerts)
