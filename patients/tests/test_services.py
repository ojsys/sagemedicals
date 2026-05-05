from datetime import date

import pytest

from patients.services import (
    _soundex,
    find_duplicates,
    generate_hospital_number,
    normalise_phone,
    validate_nigerian_phone,
)

# ── Phone normalisation ─────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("08012345678", "+2348012345678"),
    ("+2348012345678", "+2348012345678"),
    ("2348012345678", "+2348012345678"),
    ("8012345678", "+2348012345678"),
])
def test_normalise_phone(raw, expected):
    assert normalise_phone(raw) == expected


def test_validate_valid_phone():
    assert validate_nigerian_phone("08012345678") == "+2348012345678"


def test_validate_invalid_phone():
    with pytest.raises(ValueError, match="not a valid Nigerian phone"):
        validate_nigerian_phone("123")


# ── SOUNDEX ─────────────────────────────────────────────────

def test_soundex_basic():
    assert _soundex("Robert") == _soundex("Rupert")
    assert _soundex("Adaeze") != _soundex("Bello")
    assert len(_soundex("Test")) == 4


# ── Hospital number generation ───────────────────────────────

@pytest.mark.django_db(transaction=True)
def test_generate_hospital_number_format():
    from django.utils import timezone
    year = timezone.localdate().year
    num = generate_hospital_number()
    assert num.startswith(f"SAGE/{year}/")
    assert len(num.split("/")[2]) == 6


@pytest.mark.django_db(transaction=True)
def test_generate_hospital_number_sequential():
    n1 = generate_hospital_number()
    n2 = generate_hospital_number()
    seq1 = int(n1.split("/")[2])
    seq2 = int(n2.split("/")[2])
    assert seq2 == seq1 + 1


# ── Duplicate detection ──────────────────────────────────────

@pytest.mark.django_db
def test_find_duplicates_exact(django_user_model):
    from patients.models import HospitalNumberSequence, Patient
    HospitalNumberSequence.objects.create(year=2026, last_value=0)
    p = Patient.objects.create(
        hospital_number="SAGE/2026/000001",
        first_name="Hassan",
        last_name="Bello",
        date_of_birth=date(1990, 5, 15),
        sex="M",
        phone="+2348012345678",
        payer_type="self_pay",
    )
    definite, possible = find_duplicates("Hassan", "Bello", date(1990, 5, 15), "+2348012345678")
    assert p in definite


@pytest.mark.django_db
def test_find_duplicates_no_match():
    definite, possible = find_duplicates("Unique", "PersonXYZ", date(1990, 1, 1), "")
    assert not definite.exists()
    assert not possible.exists()
