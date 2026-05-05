"""
Data migration: import patients from a CSV file.

Expected CSV headers (case-insensitive):
  first_name, last_name, date_of_birth (YYYY-MM-DD), sex (M/F),
  phone, payer_type, email (optional), hospital_number (optional — generated if blank)

Usage:
  python manage.py import_patients_csv /path/to/patients.csv
  python manage.py import_patients_csv /path/to/patients.csv --dry-run
"""
import csv
import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

logger = logging.getLogger("sage")


class Command(BaseCommand):
    help = "Import patients from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="Path to the CSV file.")
        parser.add_argument("--dry-run", action="store_true", help="Validate without saving.")
        parser.add_argument(
            "--skip-duplicates", action="store_true",
            help="Skip rows where a patient with the same phone already exists.",
        )

    def handle(self, *args, **options):
        path = Path(options["csv_file"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        from patients.models import Patient
        from patients.services import (
            generate_hospital_number,
            normalise_phone,
            validate_nigerian_phone,
        )

        created = skipped = errors = 0

        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = [h.strip().lower() for h in (reader.fieldnames or [])]

            required = {"first_name", "last_name", "date_of_birth", "sex", "phone"}
            missing = required - set(headers)
            if missing:
                raise CommandError(f"CSV missing required columns: {missing}")

            for i, raw_row in enumerate(reader, start=2):
                row = {k.strip().lower(): v.strip() for k, v in raw_row.items()}
                try:
                    with transaction.atomic():
                        phone = normalise_phone(row["phone"])
                        try:
                            validate_nigerian_phone(phone)
                        except ValueError:
                            pass  # allow non-NG phones in migration context

                        if options["skip_duplicates"]:
                            if Patient.objects.filter(phone=phone, deleted_at__isnull=True).exists():
                                skipped += 1
                                continue

                        hospital_number = row.get("hospital_number", "").strip()
                        if not hospital_number:
                            hospital_number = generate_hospital_number()

                        if options["dry_run"]:
                            self.stdout.write(
                                f"Row {i}: {row['first_name']} {row['last_name']} "
                                f"({phone}) → {hospital_number}"
                            )
                            created += 1
                            continue

                        from datetime import date
                        dob = date.fromisoformat(row["date_of_birth"])
                        Patient.objects.create(
                            hospital_number=hospital_number,
                            first_name=row["first_name"].title(),
                            last_name=row["last_name"].title(),
                            date_of_birth=dob,
                            sex=row["sex"].upper()[:1],
                            phone=phone,
                            payer_type=row.get("payer_type", "self_pay") or "self_pay",
                        )
                        created += 1

                except Exception as exc:
                    errors += 1
                    logger.warning("Row %s error: %s", i, exc)
                    self.stderr.write(f"Row {i} error: {exc}")

        label = "[DRY RUN] " if options["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{label}Import complete: {created} created, "
                f"{skipped} skipped, {errors} errors."
            )
        )
