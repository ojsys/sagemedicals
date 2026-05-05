"""
Cron command: delete expired portal sessions.
Schedule: 0 2 * * * python manage.py expire_portal_sessions
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Delete expired patient portal sessions."

    def handle(self, *args, **options):
        from portal.models import PortalSession

        deleted, _ = PortalSession.objects.filter(expires_at__lt=timezone.now()).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} expired portal sessions."))
