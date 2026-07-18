import uuid
from unittest.mock import patch, MagicMock

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from org.models import (
    AssignmentRequest,
    AssignmentRequestStatus,
    Branch,
    DocumentCountProjection,
    OrganizationalResponsibility,
    OrganizationalUnit,
    OrgRole,
    Service,
    UnitType,
    OutboxEvent,
)
from org.services import (
    approve_assignment_request,
    create_assignment_request,
    reject_assignment_request,
)


def make_tree():
    """
    Technology > Technique (Pôle) > Opérationnel (Direction) > Service A
                                   > Engineering (Direction)  > Service B
    """
    root = OrganizationalUnit.add_root(name="Technology", type=UnitType.TECHNOLOGY)
    pole = root.add_child(name="Technique", type=UnitType.POLE)
    direction_ops = pole.add_child(name="Opérationnel", type=UnitType.DIRECTION)
    direction_eng = pole.add_child(name="Engineering", type=UnitType.DIRECTION)
    service_a = direction_ops.add_child(name="Service A", type=UnitType.SERVICE)
    service_b = direction_eng.add_child(name="Service B", type=UnitType.SERVICE)
    return root, pole, direction_ops, direction_eng, service_a, service_b


class OrganizationalUnitTests(TestCase):
    def test_root_must_be_technology(self):
        # is_root() n'est fiable que sur une instance réellement rattachée
        # à l'arbre (path/depth calculés par treebeard) : on crée donc une
        # vraie racine invalide via add_root(), puis on vérifie que clean()
        # la rejette a posteriori — même pattern que pour les Directions en
        # double ci-dessous.
        invalid_root = OrganizationalUnit.add_root(name="Invalide", type=UnitType.POLE)
        with self.assertRaises(ValidationError):
            invalid_root.clean()

    def test_direction_names_must_be_unique_under_same_pole(self):
        _, pole, direction_ops, *_ = make_tree()
        duplicate = pole.add_child(name="Opérationnel", type=UnitType.DIRECTION)
        with self.assertRaises(ValidationError):
            duplicate.clean()

    def test_get_branch_from_direction_and_descendants(self):
        _, _, direction_ops, direction_eng, service_a, service_b = make_tree()
        self.assertEqual(direction_ops.get_branch(), Branch.OPERATIONNEL)
        self.assertEqual(direction_eng.get_branch(), Branch.ENGINEERING)
        self.assertEqual(service_a.get_branch(), Branch.OPERATIONNEL)
        self.assertEqual(service_b.get_branch(), Branch.ENGINEERING)

    def test_get_branch_none_above_direction_level(self):
        root, pole, *_ = make_tree()
        self.assertIsNone(root.get_branch())
        self.assertIsNone(pole.get_branch())


class OrganizationalResponsibilityTests(TestCase):
    def setUp(self):
        (
            self.root,
            self.pole,
            self.direction_ops,
            self.direction_eng,
            self.service_a,
            self.service_b,
        ) = make_tree()

    def test_dos_must_be_attached_to_root(self):
        resp = OrganizationalResponsibility(
            unit=self.pole,  # incorrect : devrait être self.root
            user_id=uuid.uuid4(),
            role=OrgRole.DOS,
        )
        with self.assertRaises(ValidationError):
            resp.clean()

    def test_dos_cannot_have_a_superior(self):
        resp = OrganizationalResponsibility(
            unit=self.root,
            user_id=uuid.uuid4(),
            role=OrgRole.DOS,
            reports_to_user_id=uuid.uuid4(),
        )
        with self.assertRaises(ValidationError):
            resp.clean()

    def test_do_must_report_to_an_existing_active_dos(self):
        resp = OrganizationalResponsibility(
            unit=self.direction_ops,
            user_id=uuid.uuid4(),
            role=OrgRole.DO,
            reports_to_user_id=uuid.uuid4(),  # n'existe pas comme DOS actif
        )
        with self.assertRaises(ValidationError):
            resp.clean()

    def test_do_reporting_to_valid_dos_succeeds(self):
        dos_user = uuid.uuid4()
        OrganizationalResponsibility.objects.create(
            unit=self.root, user_id=dos_user, role=OrgRole.DOS
        )
        resp = OrganizationalResponsibility(
            unit=self.direction_ops,
            user_id=uuid.uuid4(),
            role=OrgRole.DO,
            reports_to_user_id=dos_user,
        )
        resp.clean()  # ne doit pas lever

    def test_de_cannot_report_to_a_dos(self):
        dos_user = uuid.uuid4()
        OrganizationalResponsibility.objects.create(
            unit=self.root, user_id=dos_user, role=OrgRole.DOS
        )
        resp = OrganizationalResponsibility(
            unit=self.direction_eng,
            user_id=uuid.uuid4(),
            role=OrgRole.DE,
            reports_to_user_id=dos_user,  # devrait être un DES, pas un DOS
        )
        with self.assertRaises(ValidationError):
            resp.clean()

    def test_do_role_rejected_on_engineering_direction(self):
        dos_user = uuid.uuid4()
        OrganizationalResponsibility.objects.create(
            unit=self.root, user_id=dos_user, role=OrgRole.DOS
        )
        resp = OrganizationalResponsibility(
            unit=self.direction_eng,  # branche Engineering
            user_id=uuid.uuid4(),
            role=OrgRole.DO,  # rôle de la branche Opérationnel
            reports_to_user_id=dos_user,
        )
        with self.assertRaises(ValidationError):
            resp.clean()

    def test_only_one_active_dos_in_the_whole_referential(self):
        OrganizationalResponsibility.objects.create(
            unit=self.root, user_id=uuid.uuid4(), role=OrgRole.DOS
        )
        with self.assertRaises(Exception):
            OrganizationalResponsibility.objects.create(
                unit=self.root, user_id=uuid.uuid4(), role=OrgRole.DOS
            )

    def test_full_chain_dos_do_da_cs(self):
        dos_user, do_user, da_user, cs_user = (uuid.uuid4() for _ in range(4))

        OrganizationalResponsibility.objects.create(
            unit=self.root, user_id=dos_user, role=OrgRole.DOS
        )
        OrganizationalResponsibility.objects.create(
            unit=self.direction_ops,
            user_id=do_user,
            role=OrgRole.DO,
            reports_to_user_id=dos_user,
        )
        OrganizationalResponsibility.objects.create(
            unit=self.direction_ops,
            user_id=da_user,
            role=OrgRole.DA,
            reports_to_user_id=do_user,
        )
        cs = OrganizationalResponsibility.objects.create(
            unit=self.service_a,
            user_id=cs_user,
            role=OrgRole.CS,
            reports_to_user_id=da_user,
        )
        self.assertTrue(cs.is_active)

    def test_only_one_active_cs_per_service(self):
        dos_user, do_user, da_user = (uuid.uuid4() for _ in range(3))
        OrganizationalResponsibility.objects.create(
            unit=self.root, user_id=dos_user, role=OrgRole.DOS
        )
        OrganizationalResponsibility.objects.create(
            unit=self.direction_ops,
            user_id=do_user,
            role=OrgRole.DO,
            reports_to_user_id=dos_user,
        )
        OrganizationalResponsibility.objects.create(
            unit=self.direction_ops,
            user_id=da_user,
            role=OrgRole.DA,
            reports_to_user_id=do_user,
        )
        OrganizationalResponsibility.objects.create(
            unit=self.service_a, user_id=uuid.uuid4(), role=OrgRole.CS, reports_to_user_id=da_user
        )
        with self.assertRaises(Exception):
            OrganizationalResponsibility.objects.create(
                unit=self.service_a,
                user_id=uuid.uuid4(),
                role=OrgRole.CS,
                reports_to_user_id=da_user,
            )


class AssignmentRequestTests(TestCase):
    def test_assignment_request_is_created_as_pending(self):
        root, _, direction_ops, *_ = make_tree()
        requester_id = uuid.uuid4()
        target_user_id = uuid.uuid4()

        request = create_assignment_request(
            requester_user_id=requester_id,
            target_user_id=target_user_id,
            role=OrgRole.DA,
            unit=direction_ops,
            reports_to_user_id=uuid.uuid4(),
            notes="Besoin de couverture",
        )

        self.assertIsInstance(request, AssignmentRequest)
        self.assertEqual(request.status, AssignmentRequestStatus.PENDING)
        self.assertTrue(request.is_pending)
        self.assertEqual(request.target_user_id, target_user_id)

    def test_approving_assignment_request_creates_final_assignment(self):
        root, _, direction_ops, *_ = make_tree()
        OrganizationalResponsibility.objects.create(
            unit=root, user_id=uuid.uuid4(), role=OrgRole.DOS
        )
        request = create_assignment_request(
            requester_user_id=uuid.uuid4(),
            target_user_id=uuid.uuid4(),
            role=OrgRole.DA,
            unit=direction_ops,
            reports_to_user_id=uuid.uuid4(),
        )

        approved = approve_assignment_request(request, reviewer_user_id=uuid.uuid4(), reviewer_is_admin=True)

        self.assertEqual(approved.status, AssignmentRequestStatus.APPROVED)
        self.assertTrue(OrganizationalResponsibility.objects.filter(user_id=request.target_user_id, role=OrgRole.DA).exists())

    def test_rejecting_assignment_request_leaves_no_final_assignment(self):
        _, _, direction_ops, *_ = make_tree()
        request = create_assignment_request(
            requester_user_id=uuid.uuid4(),
            target_user_id=uuid.uuid4(),
            role=OrgRole.CS,
            unit=direction_ops.add_child(name="Service X", type=UnitType.SERVICE),
            reports_to_user_id=uuid.uuid4(),
        )

        rejected = reject_assignment_request(request, reviewer_user_id=uuid.uuid4(), reviewer_is_admin=True, reason="Non conforme")

        self.assertEqual(rejected.status, AssignmentRequestStatus.REJECTED)
        self.assertFalse(OrganizationalResponsibility.objects.filter(user_id=request.target_user_id).exists())


class ServiceTests(TestCase):
    def test_service_deletion_blocked_when_documents_active(self):
        *_, service_a_unit, _ = make_tree()
        service = Service.objects.create(name="Service A", unit=service_a_unit)
        DocumentCountProjection.objects.create(service_id=service.id, active_count=3)

        self.assertFalse(service.can_be_deleted())
        with self.assertRaises(ValidationError):
            service.soft_delete()

    def test_service_deletion_allowed_when_no_active_documents(self):
        *_, service_a_unit, _ = make_tree()
        service = Service.objects.create(name="Service A", unit=service_a_unit)

        self.assertTrue(service.can_be_deleted())
        service.soft_delete()
        self.assertFalse(Service.objects.get(pk=service.pk).is_active)


class OutboxEventTests(TestCase):
    """Tests du pattern Outbox pour la garantie de livraison."""

    def test_outbox_event_created_successfully(self):
        """Vérifier qu'un événement est bien enregistré dans l'outbox."""
        event = OutboxEvent.objects.create(
            routing_key="service.created",
            payload={"id": "123", "name": "Mon Service"}
        )

        self.assertFalse(event.is_published)
        self.assertEqual(event.attempt_count, 0)
        self.assertIsNone(event.last_error)
        self.assertIsNone(event.published_at)

    def test_mark_as_published(self):
        """Vérifier que mark_as_published met à jour correctement l'événement."""
        event = OutboxEvent.objects.create(
            routing_key="service.created",
            payload={"id": "123"}
        )

        event.mark_as_published()

        # Rechargement de la DB
        event_reloaded = OutboxEvent.objects.get(pk=event.pk)
        self.assertTrue(event_reloaded.is_published)
        self.assertIsNotNone(event_reloaded.published_at)

    def test_retry_tracking(self):
        """Vérifier que le nombre de tentatives est bien tracké."""
        event = OutboxEvent.objects.create(
            routing_key="responsibility.assigned",
            payload={"user_id": "456"}
        )

        # Simuler une tentative échouée
        event.attempt_count = 1
        event.last_error = "RabbitMQ connection refused"
        event.save(update_fields=["attempt_count", "last_error"])

        event_reloaded = OutboxEvent.objects.get(pk=event.pk)
        self.assertEqual(event_reloaded.attempt_count, 1)
        self.assertEqual(event_reloaded.last_error, "RabbitMQ connection refused")

    def test_unpublished_events_query(self):
        """Vérifier que les requêtes filtrent correctement les événements non publiés."""
        # Créer plusieurs événements
        OutboxEvent.objects.create(routing_key="service.created", payload={})
        OutboxEvent.objects.create(routing_key="service.created", payload={})
        published = OutboxEvent.objects.create(routing_key="service.updated", payload={})

        # Publier un seul événement
        published.mark_as_published()

        # Vérifier le filtrage
        unpublished = OutboxEvent.objects.filter(is_published=False)
        self.assertEqual(unpublished.count(), 2)

        published_events = OutboxEvent.objects.filter(is_published=True)
        self.assertEqual(published_events.count(), 1)

    def test_publish_event_function_creates_outbox_entry(self):
        """Vérifier que publish_event() crée bien un OutboxEvent."""
        from org.events.publisher import publish_event

        # Avant
        self.assertEqual(OutboxEvent.objects.count(), 0)

        # Appeler publish_event
        publish_event("service.created", {"id": "789", "name": "Service Test"})

        # Après
        self.assertEqual(OutboxEvent.objects.count(), 1)
        event = OutboxEvent.objects.first()
        self.assertEqual(event.routing_key, "service.created")
        self.assertEqual(event.payload["id"], "789")
        self.assertFalse(event.is_published)
