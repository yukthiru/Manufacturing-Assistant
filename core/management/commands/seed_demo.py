from pathlib import Path

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand

from core.roles import ADMIN, ENGINEER, SUPERVISOR, ensure_roles
from core.samples import SAMPLES, make_pdf

DEMO_USERS = [("admin", "Admin@123", ADMIN), ("engineer", "Engineer@123", ENGINEER),
              ("supervisor", "Supervisor@123", SUPERVISOR)]


class Command(BaseCommand):
    help = "Create roles + demo users (and optionally sample PDF manuals)."

    def add_arguments(self, parser):
        parser.add_argument("--samples", action="store_true", help="write sample PDFs to ./sample_manuals")

    def handle(self, *args, **opts):
        ensure_roles()
        for username, password, role in DEMO_USERS:
            user, _ = User.objects.get_or_create(username=username)
            user.set_password(password)
            user.is_staff = user.is_superuser = (role == ADMIN)
            user.save()
            user.groups.set([Group.objects.get(name=role)])
            self.stdout.write(f"{role}: {username} / {password}")
        if opts["samples"]:
            out = Path("sample_manuals")
            out.mkdir(exist_ok=True)
            for name, pages in SAMPLES.items():
                (out / name).write_bytes(make_pdf(pages))
            self.stdout.write(f"Sample PDFs written to {out}/")
