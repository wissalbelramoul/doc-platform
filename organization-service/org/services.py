from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from .events.domain_events import emit_domain_event
from .models import (
    AssignmentRequest,
    AssignmentRequestStatus,
    EmployeeAssignment,
    OrgRole,
    Service,
)
from .permissions import _is_branch_manager


def create_assignment_request(
    *,
    requester_user_id,
    target_user_id,
    role,
    unit,
    reports_to_user_id=None,
    notes="",
) -> AssignmentRequest:
    """Create a pending assignment request that requires explicit approval."""
    with transaction.atomic():
        assignment_request = AssignmentRequest(
            requester_user_id=requester_user_id,
            target_user_id=target_user_id,
            role=role,
            unit=unit,
            reports_to_user_id=reports_to_user_id,
            notes=notes,
        )
        assignment_request.full_clean()
        assignment_request.save()

        emit_domain_event(
            "employee.assignment.requested",
            {
                "request_id": str(assignment_request.id),
                "target_user_id": str(assignment_request.target_user_id),
                "role": assignment_request.role,
                "unit_id": str(assignment_request.unit.external_id),
            },
        )
        return assignment_request


def approve_assignment_request(
    assignment_request: AssignmentRequest,
    *,
    reviewer_user_id,
    reviewer_is_admin: bool = False,
) -> AssignmentRequest:
    """Approve a pending request and create or update the final assignment."""
    with transaction.atomic():
        assignment_request = (
            AssignmentRequest.objects.select_for_update()
            .select_related("unit")
            .get(pk=assignment_request.pk)
        )
        if assignment_request.status != AssignmentRequestStatus.PENDING:
            raise ValidationError("Seule une demande en attente peut être approuvée.")

        reviewed_at = timezone.now()
        assignment_request.status = AssignmentRequestStatus.APPROVED
        assignment_request.reviewed_by_user_id = reviewer_user_id
        assignment_request.reviewed_at = reviewed_at
        assignment_request.save(update_fields=["status", "reviewed_by_user_id", "reviewed_at"])

        previous_assignment = (
            EmployeeAssignment.objects.select_for_update()
            .filter(
                user_id=assignment_request.target_user_id,
                role=assignment_request.role,
                unit=assignment_request.unit,
                ended_at__isnull=True,
            )
            .order_by("-started_at")
            .first()
        )

        if previous_assignment is not None:
            previous_assignment.ended_at = reviewed_at
            previous_assignment.save(update_fields=["ended_at"])
            emit_domain_event(
                "employee.assignment.closed",
                {
                    "assignment_id": str(previous_assignment.id),
                    "user_id": str(previous_assignment.user_id),
                    "role": previous_assignment.role,
                    "unit_id": str(previous_assignment.unit.external_id),
                },
            )

        assignment = EmployeeAssignment.objects.create(
            unit=assignment_request.unit,
            user_id=assignment_request.target_user_id,
            role=assignment_request.role,
            reports_to_user_id=assignment_request.reports_to_user_id,
            started_at=reviewed_at,
        )

        emit_domain_event(
            "employee.transferred" if previous_assignment is not None else "employee.assigned",
            {
                "assignment_id": str(assignment.id),
                "user_id": str(assignment.user_id),
                "role": assignment.role,
                "unit_id": str(assignment.unit.external_id),
            },
        )
        assignment_request.refresh_from_db()
        return assignment_request


def reject_assignment_request(
    assignment_request: AssignmentRequest,
    *,
    reviewer_user_id,
    reviewer_is_admin: bool = False,
    reason: str = "",
) -> AssignmentRequest:
    """Reject a pending assignment request without changing any final assignment."""
    with transaction.atomic():
        assignment_request = (
            AssignmentRequest.objects.select_for_update()
            .select_related("unit")
            .get(pk=assignment_request.pk)
        )
        if assignment_request.status != AssignmentRequestStatus.PENDING:
            raise ValidationError("Seule une demande en attente peut être rejetée.")

        assignment_request.status = AssignmentRequestStatus.REJECTED
        assignment_request.reviewed_by_user_id = reviewer_user_id
        assignment_request.reviewed_at = timezone.now()
        assignment_request.review_reason = reason
        assignment_request.save(update_fields=["status", "reviewed_by_user_id", "reviewed_at", "review_reason"])

        emit_domain_event(
            "employee.assignment.rejected",
            {
                "request_id": str(assignment_request.id),
                "target_user_id": str(assignment_request.target_user_id),
                "role": assignment_request.role,
                "reason": reason,
            },
        )
        assignment_request.refresh_from_db()
        return assignment_request


def can_manage_service(user, unit) -> bool:
    """Return True when the caller may create or update services in the given direction."""
    if user is None:
        return False
    if user.is_staff or user.is_superuser:
        return True
    direction = unit.get_parent()
    return _is_branch_manager(user, direction)


def create_service(*, name: str, unit, requester_user) -> Service:
    """Create a service after verifying the caller's organizational rights."""
    if not can_manage_service(requester_user, unit):
        raise PermissionDenied(
            "Seuls les administrateurs, DO/DE ou DA de la Direction concernée peuvent créer un service dans cette branche."
        )

    with transaction.atomic():
        service = Service.objects.create(name=name, unit=unit)
        emit_domain_event(
            "service.created",
            {"id": str(service.id), "name": service.name, "unit_id": str(unit.external_id)},
        )
        return service


def update_service(service: Service) -> Service:
    """Persist a service update and emit a domain event."""
    with transaction.atomic():
        service.save()
        emit_domain_event(
            "service.updated",
            {"id": str(service.id), "name": service.name, "is_active": service.is_active},
        )
        return service


def delete_service(service: Service) -> None:
    """Soft-delete a service after ensuring it contains no active documents."""
    with transaction.atomic():
        if not service.can_be_deleted():
            raise ValidationError(
                "Ce service contient encore des documents actifs et ne peut pas être supprimé."
            )
        service.soft_delete()
        emit_domain_event("service.deleted", {"id": str(service.id)})
