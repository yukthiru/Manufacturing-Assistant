from django.contrib.auth.models import Group

ADMIN = "Administrator"
ENGINEER = "Engineer"
SUPERVISOR = "Supervisor"
ROLES = [ADMIN, ENGINEER, SUPERVISOR]


def ensure_roles():
    for name in ROLES:
        Group.objects.get_or_create(name=name)


def role_of(user):
    """Return the user's single effective role name (or None)."""
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return ADMIN
    names = set(user.groups.values_list("name", flat=True))
    for role in ROLES:  # Administrator > Engineer > Supervisor if several are assigned
        if role in names:
            return role
    return None
