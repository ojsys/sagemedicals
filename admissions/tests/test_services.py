from datetime import date

import pytest
from django.utils import timezone


@pytest.fixture
def doctor(db):
    from accounts.models import User
    return User.objects.create_user(
        email="doc@test.ng", password="x", first_name="A", last_name="B"
    )


@pytest.fixture
def patient(db):
    from patients.models import Patient
    return Patient.objects.create(
        hospital_number="SAGE/2026/000001",
        first_name="Fatima", last_name="Bello",
        date_of_birth=date(1985, 3, 1), sex="F",
        phone="+2348012345678", payer_type="self_pay",
    )


@pytest.fixture
def ward(db):
    from admissions.models import Ward
    return Ward.objects.create(name="Female Medical", ward_type="Medical")


@pytest.fixture
def bed(db, ward):
    from admissions.models import Bed, Room
    room = Room.objects.create(ward=ward, name="Room 1")
    return Bed.objects.create(room=room, label="A1")


@pytest.fixture
def bed2(db, ward):
    from admissions.models import Bed, Room
    room = Room.objects.create(ward=ward, name="Room 2")
    return Bed.objects.create(room=room, label="B1")


# ── admit_patient ─────────────────────────────────────────────

@pytest.mark.django_db
def test_admit_marks_bed_occupied(patient, bed, doctor):
    from admissions.models import Bed
    from admissions.services import admit_patient
    admit_patient(patient, bed, doctor, diagnosis="Malaria")
    bed.refresh_from_db()
    assert bed.status == Bed.Status.OCCUPIED


@pytest.mark.django_db
def test_admit_creates_initial_transfer(patient, bed, doctor):
    from admissions.services import admit_patient
    admission = admit_patient(patient, bed, doctor)
    transfers = admission.transfers.all()
    assert transfers.count() == 1
    assert transfers.first().from_bed is None
    assert transfers.first().to_bed_id == bed.pk


@pytest.mark.django_db
def test_admit_rejects_occupied_bed(patient, bed, bed2, doctor):
    from admissions.models import Bed
    from admissions.services import admit_patient
    bed.status = Bed.Status.OCCUPIED
    bed.save()
    with pytest.raises(ValueError, match="not available"):
        admit_patient(patient, bed, doctor)


@pytest.mark.django_db
def test_admit_rejects_duplicate_active_admission(patient, bed, bed2, doctor):
    from admissions.services import admit_patient
    admit_patient(patient, bed, doctor)
    with pytest.raises(ValueError, match="already has an active admission"):
        admit_patient(patient, bed2, doctor)


# ── transfer_bed ──────────────────────────────────────────────

@pytest.mark.django_db
def test_transfer_frees_old_bed_and_occupies_new(patient, bed, bed2, doctor):
    from admissions.models import Bed
    from admissions.services import admit_patient, transfer_bed
    admission = admit_patient(patient, bed, doctor)
    transfer_bed(admission, bed2, doctor, reason="Closer to nurses")
    bed.refresh_from_db()
    bed2.refresh_from_db()
    assert bed.status == Bed.Status.AVAILABLE
    assert bed2.status == Bed.Status.OCCUPIED


@pytest.mark.django_db
def test_transfer_creates_transfer_record(patient, bed, bed2, doctor):
    from admissions.services import admit_patient, transfer_bed
    admission = admit_patient(patient, bed, doctor)
    transfer_bed(admission, bed2, doctor, reason="Upgrade")
    transfers = admission.transfers.order_by("created_at")
    assert transfers.count() == 2
    last = transfers.last()
    assert last.from_bed_id == bed.pk
    assert last.to_bed_id == bed2.pk


@pytest.mark.django_db
def test_transfer_rejects_occupied_target(patient, bed, bed2, doctor):
    from admissions.models import Bed
    from admissions.services import admit_patient, transfer_bed
    bed2.status = Bed.Status.OCCUPIED
    bed2.save()
    admission = admit_patient(patient, bed, doctor)
    with pytest.raises(ValueError, match="not available"):
        transfer_bed(admission, bed2, doctor)


# ── discharge_patient ─────────────────────────────────────────

@pytest.mark.django_db
def test_discharge_frees_bed(patient, bed, doctor):
    from admissions.models import Admission, Bed
    from admissions.services import admit_patient, discharge_patient
    admission = admit_patient(patient, bed, doctor)
    discharge_patient(admission, Admission.DischargeType.ROUTINE, discharged_by=doctor)
    bed.refresh_from_db()
    admission.refresh_from_db()
    assert bed.status == Bed.Status.AVAILABLE
    assert admission.status == Admission.Status.DISCHARGED


@pytest.mark.django_db
def test_discharge_rejects_already_discharged(patient, bed, doctor):
    from admissions.models import Admission
    from admissions.services import admit_patient, discharge_patient
    admission = admit_patient(patient, bed, doctor)
    discharge_patient(admission, Admission.DischargeType.ROUTINE)
    admission.refresh_from_db()
    with pytest.raises(ValueError, match="not active"):
        discharge_patient(admission, Admission.DischargeType.ROUTINE)
