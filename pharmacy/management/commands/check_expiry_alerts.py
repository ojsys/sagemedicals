"""
Cron command: notify pharmacy staff of batches expiring within N days.
Schedule: 0 7 * * 1 python manage.py check_expiry_alerts
"""
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger("sage")


class Command(BaseCommand):
    help = "Log and optionally notify about drug batches expiring soon."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=90,
            help="Alert threshold in days (default: 90).",
        )
        parser.add_argument(
            "--store", type=int, default=None,
            help="Limit to a specific store pk.",
        )

    def handle(self, *args, **options):
        from pharmacy.models import Store
        from pharmacy.services import get_expiry_alerts

        stores = Store.objects.filter(is_active=True)
        if options["store"]:
            stores = stores.filter(pk=options["store"])

        total = 0
        for store in stores:
            alerts = list(get_expiry_alerts(store, days_ahead=options["days"]))
            if alerts:
                self.stdout.write(f"\n{store.name} — {len(alerts)} expiring batch(es):")
                for b in alerts:
                    self.stdout.write(
                        f"  {b.drug} | batch {b.batch_number} | "
                        f"exp {b.expiry_date} | qty {b.quantity_remaining}"
                    )
                total += len(alerts)

        if total:
            self.stdout.write(self.style.WARNING(f"\nTotal expiry alerts: {total}"))
        else:
            self.stdout.write(self.style.SUCCESS("No expiry alerts."))
