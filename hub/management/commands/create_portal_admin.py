from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from hub.models import HubAdminUser


class Command(BaseCommand):
    help = "Create or update a portal administrator account (role: admin)."

    def add_arguments(self, parser):
        parser.add_argument("--login", required=True, help="Web login")
        parser.add_argument("--password", required=True, help="Plain password")
        parser.add_argument("--full-name", default="Администратор HUB")
        parser.add_argument(
            "--inactive",
            action="store_true",
            help="Create/update as inactive",
        )

    def handle(self, *args, **options):
        login = options["login"].strip()
        password = options["password"]
        full_name = options["full_name"].strip() or "Администратор HUB"
        if not login:
            raise CommandError("--login is required")
        if not password:
            raise CommandError("--password is required")

        admin_user, created = HubAdminUser.objects.update_or_create(
            web_login=login,
            defaults={
                "full_name": full_name,
                "web_password_hash": make_password(password),
                "is_active": not options["inactive"],
                "can_manage_users": True,
                "can_manage_briefs": True,
                "can_view_ratings": True,
            },
        )
        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Portal admin {action}: {admin_user.web_login}"))
