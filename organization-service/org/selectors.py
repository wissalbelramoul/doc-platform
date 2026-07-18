from django.db.models import Prefetch, Q

from .models import OrganizationalResponsibility, OrganizationalUnit, Service


def get_organization_tree_queryset():
    """Return the organizational tree with parents prefetched for list endpoints."""
    return OrganizationalUnit.objects.filter(is_active=True).select_related("parent")


def get_service_queryset():
    """Return active services with their organizational unit and parent prefetched."""
    return (
        Service.objects.filter(is_active=True)
        .select_related("unit")
        .prefetch_related(
            Prefetch(
                "unit__responsibilities",
                queryset=OrganizationalResponsibility.objects.filter(ended_at__isnull=True),
            )
        )
    )


def get_active_responsibilities_for_unit(unit):
    """Return active responsibilities for a unit with a single query."""
    return (
        OrganizationalResponsibility.objects.filter(unit=unit, ended_at__isnull=True)
        .select_related("unit")
    )
