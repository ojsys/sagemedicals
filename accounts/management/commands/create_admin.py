from django.core.management.base import BaseCommand

from accounts.models import Role, User


class Command(BaseCommand):
    help = "Create an initial super admin account"

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--first-name", default="Admin")
        parser.add_argument("--last-name", default="User")

    def handle(self, *args, **options):
        email = options["email"]
        if User.objects.filter(email=email).exists():
            self.stderr.write(f"User {email} already exists.")
            return
        user = User.objects.create_superuser(
            email=email,
            password=options["password"],
            first_name=options["first_name"],
            last_name=options["last_name"],
            role=Role.SUPER_ADMIN,
        )
        self.stdout.write(self.style.SUCCESS(f"Super admin created: {user.email}"))
