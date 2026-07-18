import uuid

from django.core.exceptions import ValidationError
from django.test import TestCase

from org.authentication import RemoteUser
from org.models import (
    AssignmentRequest,
    AssignmentRequestStatus,
    EmployeeAssignment,
    OrganizationalResponsibility,
    OrganizationalUnit,
    OrgRole,
    OutboxEvent,
    Service,
    UnitType,
)
from org.services import (
    approve_assignment_request,
    create_assignment_request,
    create_service,
)


class ServiceDomainTests(TestCase):
    def setUp(self):
        self.root = OrganizationalUnit.add_root(name="Technology", type=UnitType.TECHNOLOGY)
        self.pole = self.root.add_child(name="Technique", type=UnitType.POLE)
        self.direction = self.pole.add_child(name="Opérationnel", type=UnitType.DIRECTION)
        self.direction.branch = "OPERATIONNEL"
        self.direction.save()
        self.service_unit = self.direction.add_child(name="Service A", type=UnitType.SERVICE)

    def _create_dos(self, user_id):
        return OrganizationalResponsibility.objects.create(unit=self.root, user_id=user_id, role=OrgRole.DOS)

    def _create_do(self, user_id):
        return OrganizationalResponsibility.objects.create(
            unit=self.direction,
            user_id=user_id,
            role=OrgRole.DO,
            reports_to_user_id=self.dos_id,
        )

    def test_create_service_persists_and_schedules_outbox_event(self):
        self.dos_id = uuid.uuid4()
        self._create_dos(self.dos_id)

        service = create_service(
            name="Nouveau service",
            unit=self.service_unit,
            requester_user=RemoteUser(id=self.dos_id),
        )

        self.assertTrue(Service.objects.filter(pk=service.id).exists())
        self.assertTrue(OutboxEvent.objects.filter(routing_key="service.created").exists())

    def test_approve_assignment_request_creates_assignment_and_outbox_event(self):
        self.dos_id = uuid.uuid4()
        self.do_id = uuid.uuid4()
        self.target_user_id = uuid.uuid4()
        self._create_dos(self.dos_id)
        self._create_do(self.do_id)

        assignment_request = create_assignment_request(
            requester_user_id=uuid.uuid4(),
            target_user_id=self.target_user_id,
            role=OrgRole.DA,
            unit=self.direction,
            reports_to_user_id=self.do_id,
            notes="",
        )

        approve_assignment_request(
            assignment_request,
            reviewer_user_id=self.dos_id,
            reviewer_is_admin=True,
        )

        assignment_request.refresh_from_db()
        self.assertEqual(assignment_request.status, AssignmentRequestStatus.APPROVED)
        self.assertTrue(
            EmployeeAssignment.objects.filter(
                user_id=self.target_user_id,
                role=OrgRole.DA,
                unit=self.direction,
            ).exists()
        )
        self.assertTrue(OutboxEvent.objects.filter(routing_key="employee.assigned").exists())

    def test_service_save_calls_full_clean(self):
        invalid_service = Service(name="Invalid", unit=self.root)

        with self.assertRaises(ValidationError):
            invalid_service.save()
