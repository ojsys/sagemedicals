import csv
import tempfile
from pathlib import Path

import pytest


def _write_csv(rows, headers=None):
    """Write a temp CSV and return its path."""
    headers = headers or ["first_name", "last_name", "date_of_birth", "sex", "phone", "payer_type"]
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="")
    writer = csv.DictWriter(tmp, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    tmp.close()
    return tmp.name


@pytest.mark.django_db
def test_import_creates_patients():
    from django.core.management import call_command
    from patients.models import Patient

    csv_path = _write_csv([
        {"first_name": "Tunde", "last_name": "Balogun",
         "date_of_birth": "1985-06-01", "sex": "M",
         "phone": "08020000001", "payer_type": "self_pay"},
    ])
    call_command("import_patients_csv", csv_path)
    assert Patient.objects.filter(last_name="Balogun").exists()


@pytest.mark.django_db
def test_import_dry_run_does_not_create(capsys):
    from django.core.management import call_command
    from patients.models import Patient

    csv_path = _write_csv([
        {"first_name": "Dry", "last_name": "Run",
         "date_of_birth": "1990-01-01", "sex": "F",
         "phone": "08020000002", "payer_type": "self_pay"},
    ])
    call_command("import_patients_csv", csv_path, dry_run=True)
    assert not Patient.objects.filter(last_name="Run").exists()


@pytest.mark.django_db
def test_import_skip_duplicates(db):
    from django.core.management import call_command
    from patients.models import Patient

    Patient.objects.create(
        hospital_number="SAGE/2026/SKIP01",
        first_name="Existing", last_name="Patient",
        date_of_birth="1980-01-01", sex="M",
        phone="+2348020000003", payer_type="self_pay",
    )
    csv_path = _write_csv([
        {"first_name": "Existing", "last_name": "Patient",
         "date_of_birth": "1980-01-01", "sex": "M",
         "phone": "08020000003", "payer_type": "self_pay"},
    ])
    call_command("import_patients_csv", csv_path, skip_duplicates=True)
    assert Patient.objects.filter(phone="+2348020000003").count() == 1
