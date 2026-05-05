"""
Cron command: send appointment reminders for tomorrow's appointments.
Schedule via cPanel Cron: 0 18 * * * python manage.py send_appointment_reminders
"""
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger("sage")


class Command(BaseCommand):
    help = "Send SMS/email reminders for appointments scheduled for tomorrow."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Log what would be sent without actually dispatching.",
        )

    def handle(self, *args, **options):
        from datetime import timedelta

        from scheduling.models import Appointment

        tomorrow = timezone.localdate() + timedelta(days=1)
        appointments = (
            Appointment.objects.filter(
                date=tomorrow,
                status__in=["scheduled", "checked_in"],
            )
            .select_related("patient", "clinic")
        )

        sent = skipped = 0
        for appt in appointments:
            patient = appt.patient
            if not patient.phone:
                skipped += 1
                continue

            if options["dry_run"]:
                self.stdout.write(
                    f"[DRY RUN] Would remind {patient.full_name} ({patient.phone}) "
                    f"— {appt.date} {appt.slot_time} @ {appt.clinic}"
                )
                sent += 1
                continue

            from notifications.services import send_from_template
            send_from_template(
                "appointment_reminder",
                {
                    "patient_name": patient.full_name,
                    "date": str(appt.date),
                    "time": appt.slot_time.strftime("%H:%M"),
                    "clinic": str(appt.clinic),
                    "phone": patient.phone,
                },
                patient=patient,
            )
            sent += 1
            logger.info("Reminder sent to %s for appt %s", patient.phone, appt.pk)

        self.stdout.write(
            self.style.SUCCESS(
                f"Reminders: {sent} sent, {skipped} skipped (no phone)."
            )
        )
