import uuid

from rest_framework.test import APITestCase

from org.authentication import RemoteUser
from org.models import OrganizationalResponsibility, OrganizationalUnit, OrgRole, UnitType


def make_tree():
    root = OrganizationalUnit.add_root(name="Technology", type=UnitType.TECHNOLOGY)
    pole = root.add_child(name="Technique", type=UnitType.POLE)
    direction_ops = pole.add_child(name="Opérationnel", type=UnitType.DIRECTION)
    service_a = direction_ops.add_child(name="Service A", type=UnitType.SERVICE)
    return root, pole, direction_ops, service_a


class ServiceAPITests(APITestCase):
    def setUp(self):
        self.root, self.pole, self.direction_ops, self.service_a_unit = make_tree()

        self.dos_id = uuid.uuid4()
        self.do_id = uuid.uuid4()
        self.da_id = uuid.uuid4()
        self.outsider_id = uuid.uuid4()

        OrganizationalResponsibility.objects.create(
            unit=self.root, user_id=self.dos_id, role=OrgRole.DOS
        )
        OrganizationalResponsibility.objects.create(
            unit=self.direction_ops,
            user_id=self.do_id,
            role=OrgRole.DO,
            reports_to_user_id=self.dos_id,
        )
        OrganizationalResponsibility.objects.create(
            unit=self.direction_ops,
            user_id=self.da_id,
            role=OrgRole.DA,
            reports_to_user_id=self.do_id,
        )

    def _auth_as(self, user_id, is_staff=False):
        self.client.force_authenticate(
            user=RemoteUser(id=user_id, is_staff=is_staff, is_superuser=is_staff)
        )

    def test_unauthenticated_request_rejected_with_401(self):
        response = self.client.get("/api/services/")
        self.assertEqual(response.status_code, 401)

    def test_do_can_create_service_in_own_direction(self):
        self._auth_as(self.do_id)
        response = self.client.post(
            "/api/services/",
            {"name": "Nouveau Service", "unit_id": str(self.service_a_unit.external_id)},
        )
        self.assertEqual(response.status_code, 201)

    def test_da_can_create_service_in_own_direction(self):
        self._auth_as(self.da_id)
        response = self.client.post(
            "/api/services/",
            {"name": "Nouveau Service", "unit_id": str(self.service_a_unit.external_id)},
        )
        self.assertEqual(response.status_code, 201)

    def test_outsider_cannot_create_service(self):
        other_direction = self.pole.add_child(name="Engineering", type=UnitType.DIRECTION)
        other_service_unit = other_direction.add_child(name="Service X", type=UnitType.SERVICE)

        self._auth_as(self.outsider_id)
        response = self.client.post(
            "/api/services/",
            {"name": "Service X", "unit_id": str(other_service_unit.external_id)},
        )
        self.assertEqual(response.status_code, 403)

    def test_dos_has_implicit_service_management_rights_in_operationnel(self):
        # Depuis le changement de politique (cf. permissions.py), un DOS
        # a le droit de créer/modifier les services dans toutes les
        # Directions OPERATIONNEL, même réparties sur plusieurs Pôles.
        # C'est cohérent avec la hiérarchie organisationnelle.
        other_direction = self.pole.add_child(name="Autre Direction Ops", type=UnitType.DIRECTION)
        other_direction.branch = "OPERATIONNEL"  # Même branche que direction_ops
        other_direction.save()
        other_service_unit = other_direction.add_child(name="Service X", type=UnitType.SERVICE)

        self._auth_as(self.dos_id)
        response = self.client.post(
            "/api/services/",
            {"name": "Service X", "unit_id": str(other_service_unit.external_id)},
        )
        # DOS peut créer un service dans sa branche (OPERATIONNEL)
        self.assertEqual(response.status_code, 201)

    def test_dos_cannot_create_service_in_engineering_branch(self):
        # Un DOS (branche OPERATIONNEL) ne peut PAS créer de services
        # dans une Direction ENGINEERING, même s'il a des droits sur sa branche.
        engineering_direction = self.pole.add_child(name="Engineering", type=UnitType.DIRECTION)
        engineering_direction.branch = "ENGINEERING"
        engineering_direction.save()
        engineering_service_unit = engineering_direction.add_child(
            name="Eng Service", type=UnitType.SERVICE
        )

        self._auth_as(self.dos_id)
        response = self.client.post(
            "/api/services/",
            {"name": "Eng Service", "unit_id": str(engineering_service_unit.external_id)},
        )
        # DOS (OPERATIONNEL) n'a pas accès à la branche ENGINEERING
        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_service_anywhere(self):
        other_direction = self.pole.add_child(name="Engineering", type=UnitType.DIRECTION)
        other_service_unit = other_direction.add_child(name="Service X", type=UnitType.SERVICE)

        self._auth_as(uuid.uuid4(), is_staff=True)
        response = self.client.post(
            "/api/services/",
            {"name": "Service X", "unit_id": str(other_service_unit.external_id)},
        )
        self.assertEqual(response.status_code, 201)

    def test_service_deletion_conflict_when_documents_active(self):
        self._auth_as(self.do_id)
        create_response = self.client.post(
            "/api/services/",
            {"name": "Service à supprimer", "unit_id": str(self.service_a_unit.external_id)},
        )
        service_id = create_response.data["id"]

        from org.models import DocumentCountProjection

        DocumentCountProjection.objects.create(service_id=service_id, active_count=1)

        response = self.client.delete(f"/api/services/{service_id}/")
        self.assertEqual(response.status_code, 409)


class OrgUnitTreeAPITests(APITestCase):
    def setUp(self):
        self.root, self.pole, self.direction_ops, self.service_a_unit = make_tree()

    def test_tree_endpoint_returns_nested_structure_without_n_plus_1(self):
        self.client.force_authenticate(user=RemoteUser(id=uuid.uuid4(), is_staff=False))

        # 1 requête pour trouver les racines Technology + 1 requête pour
        # récupérer le sous-arbre complet de cette unique racine (via
        # get_tree()) = 2, quel que soit le nombre de nœuds dans l'arbre.
        # C'est ce nombre constant (indépendant de la profondeur/largeur)
        # qui garantit l'absence de N+1, pas un total figé à 1.
        with self.assertNumQueries(2):
            response = self.client.get("/api/org-units/tree/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["name"], "Technology")
        self.assertEqual(response.data[0]["children"][0]["name"], "Technique")
        self.assertEqual(
            response.data[0]["children"][0]["children"][0]["name"], "Opérationnel"
        )

    def test_responsibilities_endpoint_requires_admin(self):
        self.client.force_authenticate(user=RemoteUser(id=uuid.uuid4(), is_staff=False))
        response = self.client.get(
            f"/api/org-units/{self.root.external_id}/responsibilities/"
        )
        self.assertEqual(response.status_code, 403)
