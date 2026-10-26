"""
Cron command: auto-cancel lab orders not collected within LAB_ORDER_EXPIRY_HOURS (default 48).
Schedule: 0 * * * * python manage.py expire_lab_orders
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Cancel lab orders whose sample was never collected within the expiry window."

    def handle(self, *args, **options):
        from laboratory.services import LAB_ORDER_EXPIRY_HOURS, expire_stale_orders

        count = expire_stale_orders()
        self.stdout.write(self.style.SUCCESS(
            f"Expired {count} lab order{'s' if count != 1 else ''} older than {LAB_ORDER_EXPIRY_HOURS}h."
        ))
