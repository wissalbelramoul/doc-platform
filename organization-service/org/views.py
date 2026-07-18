from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .events.domain_events import emit_domain_event
from .models import AssignmentRequest, OrganizationalResponsibility, OrganizationalUnit, Service, UnitType
from .permissions import IsAdmin, IsAdminOrBranchManager
from .selectors import get_active_responsibilities_for_unit, get_service_queryset
from .serializers import (
    AssignmentRequestSerializer,
    OrganizationalResponsibilitySerializer,
    OrganizationalUnitSerializer,
    ServiceSerializer,
)
from .services import (
    approve_assignment_request,
    create_assignment_request,
    create_service,
    delete_service,
    reject_assignment_request,
    update_service,
)


class OrganizationalUnitViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Lecture seule : le document ne prévoit pas de création/modification
    d'unités via l'API publique (seul le sous-endpoint /responsibilities/
    accepte un POST). Les unités sont créées via l'admin Django ou des
    scripts de migration, où `full_clean()` est invoqué (cf. models.py).
    """

    queryset = OrganizationalUnit.objects.filter(is_active=True)
    serializer_class = OrganizationalUnitSerializer
    lookup_field = "external_id"

    def get_serializer_context(self):
        """Populate parent ids from the current queryset without triggering N+1 lookups."""
        context = super().get_serializer_context()
        queryset = (
            self.paginated_queryset
            if hasattr(self, "paginated_queryset") and self.paginated_queryset is not None
            else self.get_queryset()
        )

        queryset_list = list(queryset)
        if queryset_list:
            nodes_by_path = {node.path: node for node in queryset_list}
            parent_ids = {}
            steplen = OrganizationalUnit.steplen
            for node in queryset_list:
                if node.is_root():
                    parent_ids[node.id] = None
                    continue

                parent_path = node.path[:-steplen] if len(node.path) > steplen else None
                parent_node = nodes_by_path.get(parent_path)
                parent_ids[node.id] = str(parent_node.external_id) if parent_node else None

            context["parent_ids"] = parent_ids

        return context

    @action(detail=False, methods=["get"], url_path="tree")
    def tree(self, request):
        roots = OrganizationalUnit.get_root_nodes().filter(
            type=UnitType.TECHNOLOGY, is_active=True
        )
        forest = [self._build_subtree(root) for root in roots]
        return Response(forest)

    @staticmethod
    def _build_subtree(root):
        """
        Construit la structure imbriquée en une seule requête SQL par
        racine (grâce au Materialized Path) puis assemble le résultat en
        mémoire, sans requête supplémentaire par nœud — cohérent avec la
        justification de performance du document (§4.5).
        """
        nodes = list(OrganizationalUnit.get_tree(root).filter(is_active=True))
        steplen = OrganizationalUnit.steplen

        by_path = {
            node.path: {
                "external_id": str(node.external_id),
                "name": node.name,
                "type": node.type,
                "is_active": node.is_active,
                "children": [],
            }
            for node in nodes
        }
        for node in nodes:
            parent_path = node.path[:-steplen]
            if parent_path in by_path:
                by_path[parent_path]["children"].append(by_path[node.path])

        return by_path[nodes[0].path]

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="responsibilities",
        permission_classes=[IsAdmin],
    )
    def responsibilities(self, request, external_id=None):
        unit = self.get_object()

        if request.method == "GET":
            qs = get_active_responsibilities_for_unit(unit)
            role_filter = request.query_params.get("role")
            if role_filter:
                qs = qs.filter(role__in=role_filter.split(","))
            serializer = OrganizationalResponsibilitySerializer(qs, many=True)
            return Response(serializer.data)

        payload = request.data.copy()
        payload["unit_id"] = str(unit.external_id)
        serializer = OrganizationalResponsibilitySerializer(data=payload)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                responsibility = serializer.save()
                emit_domain_event(
                    "responsibility.assigned",
                    {
                        "id": str(responsibility.id),
                        "unit_id": str(unit.external_id),
                        "user_id": str(responsibility.user_id),
                        "role": responsibility.role,
                    },
                )
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        except IntegrityError:
            return Response(
                {
                    "detail": "Conflit : cette responsabilité viole une contrainte "
                    "d'unicité (ex. rôle déjà actif sur cette unité)."
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            OrganizationalResponsibilitySerializer(responsibility).data,
            status=status.HTTP_201_CREATED,
        )


class AssignmentRequestViewSet(viewsets.ModelViewSet):
    queryset = AssignmentRequest.objects.all()
    serializer_class = AssignmentRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AssignmentRequest.objects.all()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment_request = create_assignment_request(
            requester_user_id=request.user.id,
            target_user_id=serializer.validated_data["target_user_id"],
            role=serializer.validated_data["role"],
            unit=serializer.validated_data["unit"],
            reports_to_user_id=serializer.validated_data.get("reports_to_user_id"),
            notes=serializer.validated_data.get("notes", ""),
        )
        serializer = self.get_serializer(assignment_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("Seuls les administrateurs peuvent approuver une demande d'affectation.")
        assignment_request = self.get_object()
        approve_assignment_request(
            assignment_request,
            reviewer_user_id=request.user.id,
            reviewer_is_admin=True,
        )
        return Response(self.get_serializer(assignment_request).data)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("Seuls les administrateurs peuvent rejeter une demande d'affectation.")
        assignment_request = self.get_object()
        reject_assignment_request(
            assignment_request,
            reviewer_user_id=request.user.id,
            reviewer_is_admin=True,
            reason=request.data.get("reason", ""),
        )
        return Response(self.get_serializer(assignment_request).data)


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = get_service_queryset()
    serializer_class = ServiceSerializer
    permission_classes = [IsAdminOrBranchManager]
    lookup_field = "id"

    def perform_create(self, serializer):
        unit = serializer.validated_data["unit"]
        service = create_service(name=serializer.validated_data["name"], unit=unit, requester_user=self.request.user)
        serializer.instance = service

    def perform_update(self, serializer):
        service = serializer.save()
        update_service(service)

    def destroy(self, request, *args, **kwargs):
        service = self.get_object()
        try:
            delete_service(service)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)
