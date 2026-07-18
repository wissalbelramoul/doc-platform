"""
Modèle de données du microservice Organisation.

IMPORTANT — hiérarchie à 4 niveaux de responsabilité (cf. rapport, §4.1) :

    DOS (branche Opérationnel)  ─┐
    DES (branche Engineering)   ─┴─> DO / DE ─> DA ─> Chef de Service

`OrganizationalUnit` reste un arbre à 4 niveaux (Technology > Pôle >
Direction > Service) : la hiérarchie *humaine* ci-dessus est représentée
séparément dans `OrganizationalResponsibility`, comme le justifie le
document d'origine.

Point d'attention : ni DOS ni DES ne correspondent à une unité de l'arbre
(un DOS supervise des DO répartis sur plusieurs Pôles). Faute de niveau
"branche" dans l'arbre, ils sont rattachés conventionnellement à la racine
Technology (Option A du rapport). Voir `TOP_LEVEL_ROLES` plus bas.
"""

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from treebeard.mp_tree import MP_Node


class UnitType(models.TextChoices):
    TECHNOLOGY = "TECHNOLOGY", "Technology"
    POLE = "POLE", "Pôle"
    DIRECTION = "DIRECTION", "Direction"
    SERVICE = "SERVICE", "Service"


# Ordre imposé des niveaux (cf. §4.5 du document).
UNIT_TYPE_ORDER = [
    UnitType.TECHNOLOGY,
    UnitType.POLE,
    UnitType.DIRECTION,
    UnitType.SERVICE,
]


class Branch(models.TextChoices):
    """Branche métier humaine : Opérationnel ou Engineering."""

    OPERATIONNEL = "OPERATIONNEL", "Opérationnel"
    ENGINEERING = "ENGINEERING", "Engineering"



class OrgRole(models.TextChoices):
    DOS = "DOS", "Directeur des Opérations"
    DES = "DES", "Directeur Engineering"
    DO = "DO", "Directeur Opérationnel"
    DE = "DE", "Directeur Engineering"
    DA = "DA", "Directeur Adjoint"
    CS = "CS", "Chef de Service"


TOP_LEVEL_ROLES = {
    OrgRole.DOS,
    OrgRole.DES,
}

ROLE_BRANCH_MAP = {
    OrgRole.DOS: Branch.OPERATIONNEL,
    OrgRole.DO: Branch.OPERATIONNEL,
    OrgRole.DES: Branch.ENGINEERING,
    OrgRole.DE: Branch.ENGINEERING,
}


class OrganizationalUnit(MP_Node):
    external_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=UnitType.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    branch = models.CharField(
        max_length=20,
        choices=Branch.choices,
        null=True,
        blank=True,
        help_text="Défini uniquement pour les Directions."
    )

    node_order_by = ["name"]

    class Meta:
        indexes = [
            models.Index(fields=["type"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.get_type_display()} — {self.name}"

    def clean(self):
        """
        Validation des règles métier de l'arbre organisationnel.
        """
        super().clean()

        if self.is_root():
            if self.type != UnitType.TECHNOLOGY:
                raise ValidationError(
                    "Seule une unité de type Technology peut être la racine."
                )
            return

        parent = self.get_parent()
        expected_parent_type = self._expected_parent_type()

        if parent is None or parent.type != expected_parent_type:
            raise ValidationError(
                f"Une unité de type {self.type} doit avoir un parent de type "
                f"{expected_parent_type}."
            )

        # Validation du champ branch
        if self.type == UnitType.DIRECTION:
            if not self.branch:
                raise ValidationError({
                    "branch": (
                        "Une Direction doit appartenir à une branche "
                        "(Opérationnel ou Engineering)."
                    )
                })
        else:
            self.branch = None

        # Deux Directions de même nom sous un même Pôle interdites
        if self.type == UnitType.DIRECTION:
            siblings = parent.get_children().filter(
                type=UnitType.DIRECTION,
                name__iexact=self.name,
            )

            if self.pk:
                siblings = siblings.exclude(pk=self.pk)

            if siblings.exists():
                raise ValidationError(
                    "Deux Directions portant le même nom ne peuvent pas "
                    "coexister sous un même Pôle."
                )

    def save(self, *args, **kwargs):
        """
        Exécute toujours les validations avant sauvegarde.
        """
        self.full_clean()
        super().save(*args, **kwargs)

    def _expected_parent_type(self):
        idx = UNIT_TYPE_ORDER.index(self.type)
        if idx == 0:
            return None
        return UNIT_TYPE_ORDER[idx - 1]

    def get_branch(self):
        """
        Retourne la branche de l'unité.

        - Une Direction retourne directement son champ `branch`.
        - Un Service hérite de la branche de sa Direction parente.
        - Technology et Pôle retournent None.
        """

        if self.type == UnitType.DIRECTION:
            return self.branch

        direction = (
            self.get_ancestors()
            .filter(type=UnitType.DIRECTION)
            .last()
        )

        if direction:
            return direction.branch

        return None


class OrganizationalResponsibility(models.Model):
    """A business responsibility assigned to a user for an organizational unit."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit = models.ForeignKey(
        OrganizationalUnit,
        on_delete=models.PROTECT,
        related_name="responsibilities",
    )
    user_id = models.UUIDField()
    role = models.CharField(max_length=3, choices=OrgRole.choices)
    reports_to_user_id = models.UUIDField(null=True, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["unit", "role", "ended_at"]),
            models.Index(fields=["user_id"]),
        ]
        constraints = [
            # Un seul DOS actif dans tout le référentiel.
            models.UniqueConstraint(
                fields=["role"],
                condition=models.Q(role=OrgRole.DOS, ended_at__isnull=True),
                name="unique_active_dos",
            ),
            # Un seul DES actif dans tout le référentiel.
            models.UniqueConstraint(
                fields=["role"],
                condition=models.Q(role=OrgRole.DES, ended_at__isnull=True),
                name="unique_active_des",
            ),
            # Un seul DO (ou DE) actif par Direction.
            models.UniqueConstraint(
                fields=["unit", "role"],
                condition=models.Q(role__in=[OrgRole.DO, OrgRole.DE], ended_at__isnull=True),
                name="unique_active_do_de_per_direction",
            ),
            # Un seul Chef de Service actif par Service.
            models.UniqueConstraint(
                fields=["unit", "role"],
                condition=models.Q(role=OrgRole.CS, ended_at__isnull=True),
                name="unique_active_cs_per_service",
            ),
        ]

    def __str__(self):
        return f"{self.get_role_display()} — {self.user_id} ({self.unit})"

    @property
    def is_active(self):
        return self.ended_at is None

    def clean(self):
        super().clean()
        self._validate_unit_type_for_role()
        self._validate_branch_consistency()
        self._validate_reports_to()

    def _validate_unit_type_for_role(self):
        if self.role in TOP_LEVEL_ROLES:
            if self.unit.type != UnitType.TECHNOLOGY:
                raise ValidationError(
                    "Un DOS ou un DES doit être rattaché à l'unité racine "
                    "Technology (aucune unité de branche n'existe dans l'arbre)."
                )
        elif self.role in (OrgRole.DO, OrgRole.DE, OrgRole.DA):
            if self.unit.type != UnitType.DIRECTION:
                raise ValidationError(
                    f"Un {self.role} doit être rattaché à une unité de type Direction."
                )
        elif self.role == OrgRole.CS:
            if self.unit.type != UnitType.SERVICE:
                raise ValidationError(
                    "Un Chef de Service doit être rattaché à une unité de type Service."
                )

    def _validate_branch_consistency(self):
        if self.role in (OrgRole.DO, OrgRole.DE):
            expected_branch = ROLE_BRANCH_MAP[self.role]
            actual_branch = self.unit.get_branch()
            if actual_branch != expected_branch:
                raise ValidationError(
                    f"Le rôle {self.role} n'est pas cohérent avec la branche "
                    f"de la Direction ({actual_branch})."
                )

    def _validate_reports_to(self):
        if self.role in TOP_LEVEL_ROLES:
            if self.reports_to_user_id is not None:
                raise ValidationError(
                    "Un DOS ou un DES est au sommet de la chaîne hiérarchique "
                    "et ne peut pas avoir de supérieur."
                )
            return

        if self.reports_to_user_id is None:
            raise ValidationError(
                f"Le rôle {self.role} doit obligatoirement indiquer son "
                "supérieur hiérarchique (reports_to_user_id)."
            )

        if self.role in (OrgRole.DO, OrgRole.DE):
            expected_role = OrgRole.DOS if self.role == OrgRole.DO else OrgRole.DES
            ok = OrganizationalResponsibility.objects.filter(
                user_id=self.reports_to_user_id, role=expected_role, ended_at__isnull=True
            ).exists()
            if not ok:
                raise ValidationError(
                    f"Le supérieur désigné doit avoir le rôle actif {expected_role} "
                    f"(un {self.role} ne peut reporter qu'à un {expected_role})."
                )

        elif self.role == OrgRole.DA:
            branch = self.unit.get_branch()
            expected_role = OrgRole.DO if branch == Branch.OPERATIONNEL else OrgRole.DE
            ok = OrganizationalResponsibility.objects.filter(
                user_id=self.reports_to_user_id,
                role=expected_role,
                unit=self.unit,
                ended_at__isnull=True,
            ).exists()
            if not ok:
                raise ValidationError(
                    f"Le supérieur désigné doit être {expected_role} actif de "
                    "la même Direction."
                )

        elif self.role == OrgRole.CS:
            direction = self.unit.get_parent()
            ok = OrganizationalResponsibility.objects.filter(
                user_id=self.reports_to_user_id,
                role=OrgRole.DA,
                unit=direction,
                ended_at__isnull=True,
            ).exists()
            if not ok:
                raise ValidationError(
                    "Le supérieur désigné doit être un Directeur Adjoint actif "
                    "de la Direction parente du Service."
                )


class EmployeeAssignment(models.Model):
    """Finalized employee assignment used by the organization service.

    The assignment lifecycle is driven by an approval workflow via
    AssignmentRequest. Only approved assignments are persisted here.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit = models.ForeignKey(
        OrganizationalUnit,
        on_delete=models.PROTECT,
        related_name="employee_assignments",
    )
    user_id = models.UUIDField()
    role = models.CharField(max_length=3, choices=OrgRole.choices)
    reports_to_user_id = models.UUIDField(null=True, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["unit", "role", "ended_at"]),
            models.Index(fields=["user_id"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "role", "unit", "ended_at"],
                condition=models.Q(ended_at__isnull=True),
                name="unique_active_assignment_per_user_role_unit",
            ),
        ]

    def __str__(self):
        return f"{self.get_role_display()} — {self.user_id} ({self.unit})"

    @property
    def is_active(self):
        return self.ended_at is None

    def clean(self):
        super().clean()
        if self.role in TOP_LEVEL_ROLES:
            if self.unit.type != UnitType.TECHNOLOGY:
                raise ValidationError("Un DOS ou un DES doit être rattaché à la racine Technology.")
        elif self.role in (OrgRole.DO, OrgRole.DE, OrgRole.DA):
            if self.unit.type != UnitType.DIRECTION:
                raise ValidationError("Un rôle de direction doit être rattaché à une Direction.")
        elif self.role == OrgRole.CS:
            if self.unit.type != UnitType.SERVICE:
                raise ValidationError("Un Chef de Service doit être rattaché à un Service.")

        if self.role in (OrgRole.DO, OrgRole.DE):
            expected_branch = ROLE_BRANCH_MAP[self.role]
            if self.unit.get_branch() != expected_branch:
                raise ValidationError("La branche de l'unité ne correspond pas au rôle demandé.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class AssignmentRequestStatus(models.TextChoices):
    PENDING = "PENDING", "En attente"
    APPROVED = "APPROVED", "Approuvée"
    REJECTED = "REJECTED", "Rejetée"


class AssignmentRequest(models.Model):
    """Pending assignment request that requires explicit admin approval."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester_user_id = models.UUIDField()
    target_user_id = models.UUIDField()
    role = models.CharField(max_length=3, choices=OrgRole.choices)
    unit = models.ForeignKey(
        OrganizationalUnit,
        on_delete=models.PROTECT,
        related_name="assignment_requests",
    )
    reports_to_user_id = models.UUIDField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=AssignmentRequestStatus.choices,
        default=AssignmentRequestStatus.PENDING,
    )
    reviewed_by_user_id = models.UUIDField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["target_user_id"]),
        ]

    @property
    def is_pending(self):
        return self.status == AssignmentRequestStatus.PENDING

    def clean(self):
        super().clean()
        if self.role in TOP_LEVEL_ROLES:
            if self.unit.type != UnitType.TECHNOLOGY:
                raise ValidationError("Une demande de DOS/DES doit pointer vers la racine Technology.")
        elif self.role in (OrgRole.DO, OrgRole.DE, OrgRole.DA):
            if self.unit.type != UnitType.DIRECTION:
                raise ValidationError("Une demande de direction doit pointer vers une Direction.")
        elif self.role == OrgRole.CS:
            if self.unit.type != UnitType.SERVICE:
                raise ValidationError("Une demande de Chef de Service doit pointer vers un Service.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Service(models.Model):
    """Service exposed by the organization service.

    This model intentionally remains a lightweight wrapper around the
    organizational tree. It reuses the existing OrganizationalUnit model rather
    than introducing a parallel hierarchy.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    unit = models.OneToOneField(
        OrganizationalUnit,
        on_delete=models.PROTECT,
        related_name="service",
        limit_choices_to={"type": UnitType.SERVICE},
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.unit.type != UnitType.SERVICE:
            raise ValidationError(
                "Un Service ne peut être associé qu'à une unité organisationnelle "
                "de type SERVICE."
            )

    def active_document_count(self):
        projection = DocumentCountProjection.objects.filter(service_id=self.id).first()
        return projection.active_count if projection else 0

    def can_be_deleted(self):
        return self.active_document_count() == 0

    def soft_delete(self):
        if not self.can_be_deleted():
            raise ValidationError(
                "Un service contenant des documents actifs ne peut pas être supprimé."
            )
        self.is_active = False
        self.save(update_fields=["is_active"])


class DocumentCountProjection(models.Model):
    """Projection locale alimentée par les événements document.created/deleted."""

    service_id = models.UUIDField(primary_key=True)
    active_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.service_id} — {self.active_count} document(s) actif(s)"


class OutboxEvent(models.Model):
    """
    Outbox pattern : événements en attente de publication.
    
    Table locale garantissant la livraison des événements même en cas
    d'indisponibilité RabbitMQ. Un process dédié traite les événements
    non publiés avec retry et backoff exponentiel.
    
    Voir org/management/commands/process_outbox.py
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    routing_key = models.CharField(max_length=255)
    payload = models.JSONField()
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_published", "created_at"]),
        ]
        ordering = ["created_at"]

    def __str__(self):
        status = "✓ Publié" if self.is_published else "⏳ En attente"
        return f"{self.routing_key} ({status}) — {self.created_at}"

    def mark_as_published(self):
        """Marque l'événement comme publié."""
        self.is_published = True
        self.published_at = timezone.now()
        self.save(update_fields=["is_published", "published_at"])
