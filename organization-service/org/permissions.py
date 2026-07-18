from rest_framework import permissions

from .models import OrganizationalResponsibility, OrgRole, Branch


def _is_branch_manager(user, direction_unit):
    """
    Vrai si `user` est autorisé à gérer les services de la Direction donnée.

    Incluent les rôles suivants :
    - DO/DE/DA actif de cette Direction
    - DOS actif si la Direction est en branche OPERATIONNEL
    - DES actif si la Direction est en branche ENGINEERING

    Les DOS/DES sont désormais inclus (cf. rapport §4.7 clarification) :
    un DOS supervise toutes les Directions Opérationnel, même réparties sur
    plusieurs Pôles ; accorder l'accès par défaut est cohérent avec la
    hiérarchie organisationnelle.
    """
    if direction_unit is None:
        return False

    # Cas 1 : DO/DE/DA actif de cette Direction
    if OrganizationalResponsibility.objects.filter(
        unit=direction_unit,
        user_id=user.id,
        role__in=[OrgRole.DO, OrgRole.DE, OrgRole.DA],
        ended_at__isnull=True,
    ).exists():
        return True

    # Cas 2 : DOS pour Direction OPERATIONNEL, ou DES pour Direction ENGINEERING
    direction_branch = direction_unit.get_branch()
    if direction_branch == Branch.OPERATIONNEL:
        return OrganizationalResponsibility.objects.filter(
            user_id=user.id,
            role=OrgRole.DOS,
            ended_at__isnull=True,
        ).exists()
    elif direction_branch == Branch.ENGINEERING:
        return OrganizationalResponsibility.objects.filter(
            user_id=user.id,
            role=OrgRole.DES,
            ended_at__isnull=True,
        ).exists()

    return False


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )


class IsAdminOrBranchManager(permissions.BasePermission):
    """
    Lecture : tout utilisateur authentifié.
    Écriture : administrateurs, ou responsables de branche (DO/DE/DA de la Direction
    parente, ou DOS/DES si la branche correspond).

    La création est un cas particulier : il n'existe pas encore d'objet sur
    lequel appliquer `has_object_permission`, donc la vérification précise
    est faite explicitement dans `ServiceViewSet.perform_create()`.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_staff or request.user.is_superuser:
            return True
        direction = obj.unit.get_parent()
        return _is_branch_manager(request.user, direction)
