from datetime import date

import pytest


@pytest.fixture
def patient(db):
    from patients.models import Patient
    return Patient.objects.create(
        hospital_number="SAGE/2026/000099",
        first_name="Test", last_name="Patient",
        date_of_birth=date(1985, 1, 1), sex="M",
        phone="+2348099999999", payer_type="self_pay",
    )


@pytest.fixture
def amoxicillin(db):
    from prescriptions.models import Drug
    return Drug.objects.create(
        generic_name="Amoxicillin", strength="500mg", dosage_form="capsule",
        category="pom", is_formulary=True,
    )


@pytest.fixture
def ibuprofen(db):
    from prescriptions.models import Drug
    return Drug.objects.create(
        generic_name="Ibuprofen", strength="400mg", dosage_form="tablet",
        category="otc", is_formulary=True,
    )


@pytest.fixture
def naproxen(db):
    from prescriptions.models import Drug
    return Drug.objects.create(
        generic_name="Naproxen", strength="500mg", dosage_form="tablet",
        category="pom", is_formulary=True,
    )


# ── Allergy checks ────────────────────────────────────────────

@pytest.mark.django_db
def test_allergy_check_hits(patient, amoxicillin):
    from patients.models import Allergy
    from prescriptions.services import check_allergy
    Allergy.objects.create(
        patient=patient, allergen="Amoxicillin",
        allergy_type="drug", severity="severe", is_active=True,
    )
    result = check_allergy(patient, amoxicillin)
    assert result is not None
    assert result.allergen == "Amoxicillin"


@pytest.mark.django_db
def test_allergy_check_no_match(patient, ibuprofen):
    from patients.models import Allergy
    from prescriptions.services import check_allergy
    Allergy.objects.create(
        patient=patient, allergen="Penicillin",
        allergy_type="drug", severity="moderate", is_active=True,
    )
    result = check_allergy(patient, ibuprofen)
    assert result is None


@pytest.mark.django_db
def test_allergy_check_inactive_ignored(patient, amoxicillin):
    from patients.models import Allergy
    from prescriptions.services import check_allergy
    Allergy.objects.create(
        patient=patient, allergen="Amoxicillin",
        allergy_type="drug", severity="severe", is_active=False,
    )
    result = check_allergy(patient, amoxicillin)
    assert result is None


# ── Interaction checks ────────────────────────────────────────

@pytest.mark.django_db
def test_interaction_check_detected(patient, ibuprofen, naproxen):
    from django.utils import timezone

    from accounts.models import User
    from encounters.models import Encounter
    from prescriptions.models import DrugInteraction, Prescription
    from prescriptions.services import check_interactions

    doctor = User.objects.create_user(email="doc@test.ng", password="x", first_name="D", last_name="O")
    enc = Encounter.objects.create(patient=patient, attending=doctor, date_time=timezone.now())
    DrugInteraction.objects.create(
        drug_a=ibuprofen, drug_b=naproxen,
        severity="severe", description="Dual NSAID — increased GI bleed risk",
    )
    active_rx = [
        Prescription(drug=ibuprofen, patient=patient, encounter=enc,
                     prescriber=doctor, dose="400mg", quantity=10, status="pending")
    ]
    interactions = check_interactions(naproxen, active_rx)
    assert len(interactions) == 1
    assert interactions[0][1].severity == "severe"


@pytest.mark.django_db
def test_interaction_check_no_interaction(patient, ibuprofen, amoxicillin):
    from prescriptions.services import check_interactions
    active_rx = []
    interactions = check_interactions(amoxicillin, active_rx)
    assert interactions == []
