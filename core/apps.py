from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _create_roles(sender, **kwargs):
    from .roles import ensure_roles
    ensure_roles()


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        post_migrate.connect(_create_roles, sender=self, dispatch_uid="core_create_roles")
