import re

from django.db import transaction
from django.db.models import Q
from django.utils import timezone


def generate_hospital_number():
    """Generate the next SAGE/YYYY/NNNNNN number. Race-safe via SELECT FOR UPDATE."""
    from patients.models import HospitalNumberSequence, Patient
    from django.db import transaction, models

    year = timezone.localdate().year
    with transaction.atomic():
        seq, _ = HospitalNumberSequence.objects.select_for_update().get_or_create(
            year=year, defaults={"last_value": 0}
        )

        # Find the highest existing hospital number for the current year in Patient table
        # and update the sequence if it's behind.
        prefix = f"SAGE/{year}/"
        max_patient_number = Patient.objects.filter(
            hospital_number__startswith=prefix
        ).aggregate(max_num=models.Max("hospital_number"))["max_num"]

        if max_patient_number:
            try:
                # Extract the numeric part from the max_patient_number
                current_max_numeric = int(max_patient_number.split("/")[-1])
                if current_max_numeric > seq.last_value:
                    seq.last_value = current_max_numeric
            except (ValueError, IndexError):
                # Handle cases where existing hospital_number might not conform to expected format
                # For robustness, we'll just log and proceed without updating based on malformed numbers
                pass # You might want to log this in a real application

        seq.last_value += 1
        seq.save(update_fields=["last_value"])
        return f"SAGE/{year}/{seq.last_value:06d}"


def _soundex(name):
    """American Soundex — works on both SQLite and MySQL for local duplicate detection."""
    if not name:
        return ""
    name = name.upper()
    codes = {"BFPV": "1", "CGJKQSXYZ": "2", "DT": "3", "L": "4", "MN": "5", "R": "6"}
    result = name[0]
    prev = ""
    for ch in name[1:]:
        code = "0"
        for letters, digit in codes.items():
            if ch in letters:
                code = digit
                break
        if code != "0" and code != prev:
            result += code
        prev = code
    return (result + "000")[:4]


def find_duplicates(first_name, last_name, date_of_birth, phone, exclude_pk=None):
    """Return (definite, possible) querysets of potential duplicate patients."""
    from patients.models import Patient

    qs = Patient.objects.filter(is_active=True)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    # Definite: same normalised full name + same DOB
    fn_norm = first_name.strip().lower()
    ln_norm = last_name.strip().lower()
    definite = qs.filter(
        first_name__iexact=fn_norm,
        last_name__iexact=ln_norm,
        date_of_birth=date_of_birth,
    )

    # Possible: same phone OR prefix-similar name + same DOB
    possible_q = Q()
    if phone:
        clean_phone = re.sub(r"\D", "", phone)
        possible_q |= Q(phone__endswith=clean_phone[-8:])
    possible_q |= Q(
        date_of_birth=date_of_birth,
        first_name__istartswith=first_name[:2] if len(first_name) >= 2 else first_name,
        last_name__istartswith=last_name[:2] if len(last_name) >= 2 else last_name,
    )
    possible = qs.filter(possible_q).exclude(pk__in=definite)

    return definite, possible


def normalise_phone(phone):
    """Normalise a Nigerian phone number to +234XXXXXXXXXX format."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("234") and len(digits) == 13:
        return f"+{digits}"
    if digits.startswith("0") and len(digits) == 11:
        return f"+234{digits[1:]}"
    if len(digits) == 10:
        return f"+234{digits}"
    return phone


def validate_nigerian_phone(phone):
    """Return normalised phone or raise ValueError."""
    normalised = normalise_phone(phone)
    pattern = re.compile(r"^\+234[789][01]\d{8}$")
    if not pattern.match(normalised):
        raise ValueError(f"'{phone}' is not a valid Nigerian phone number.")
    return normalised
