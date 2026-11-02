from rest_framework.permissions import BasePermission

from .roles import ADMIN, ENGINEER, SUPERVISOR, role_of


class IsAdministrator(BasePermission):
    message = "Administrator role required."

    def has_permission(self, request, view):
        return role_of(request.user) == ADMIN


class IsEngineer(BasePermission):
    message = "Engineer role required."

    def has_permission(self, request, view):
        return role_of(request.user) == ENGINEER


class IsSupervisorOrAdmin(BasePermission):
    message = "Supervisor or Administrator role required."

    def has_permission(self, request, view):
        return role_of(request.user) in (SUPERVISOR, ADMIN)


class CanViewQueryHistory(BasePermission):
    message = "A recognized application role is required."

    def has_permission(self, request, view):
        return role_of(request.user) in (ADMIN, ENGINEER, SUPERVISOR)
