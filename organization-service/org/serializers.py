from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import (
    AssignmentRequest,
    AssignmentRequestStatus,
    OrganizationalResponsibility,
    OrganizationalUnit,
    Service,
    UnitType,
)


class OrganizationalUnitSerializer(serializers.ModelSerializer):
    parent_id = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationalUnit
        fields = [
            "external_id",
            "name",
            "type",
            "is_active",
            "parent_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["external_id", "created_at", "updated_at"]

    def get_parent_id(self, obj):
        # Optimisation N+1 : utiliser le cache pré-chargé en contexte
        # au lieu d'appeler get_parent() qui cause une requête SQL
        parent_ids = self.context.get('parent_ids', {})
        if parent_ids and obj.id in parent_ids:
            return parent_ids[obj.id]

        # Fallback si pas de contexte (ex. direct instantiation)
        parent = obj.get_parent()
        return str(parent.external_id) if parent else None


class OrganizationalResponsibilitySerializer(serializers.ModelSerializer):
    unit_id = serializers.SlugRelatedField(
        source="unit",
        slug_field="external_id",
        queryset=OrganizationalUnit.objects.all(),
    )
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = OrganizationalResponsibility
        fields = [
            "id",
            "unit_id",
            "user_id",
            "role",
            "reports_to_user_id",
            "started_at",
            "ended_at",
            "is_active",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        """Run business validation before the object is persisted."""
        instance = OrganizationalResponsibility(**attrs)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict or exc.messages) from exc
        return attrs


class AssignmentRequestSerializer(serializers.ModelSerializer):
    unit_id = serializers.SlugRelatedField(
        source="unit",
        slug_field="external_id",
        queryset=OrganizationalUnit.objects.all(),
    )

    class Meta:
        model = AssignmentRequest
        fields = [
            "id",
            "requester_user_id",
            "target_user_id",
            "role",
            "unit_id",
            "reports_to_user_id",
            "notes",
            "status",
            "reviewed_by_user_id",
            "reviewed_at",
            "review_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "reviewed_by_user_id", "reviewed_at", "review_reason", "created_at", "updated_at"]


class ServiceSerializer(serializers.ModelSerializer):
    unit_id = serializers.SlugRelatedField(
        source="unit",
        slug_field="external_id",
        queryset=OrganizationalUnit.objects.filter(type=UnitType.SERVICE),
    )
    active_document_count = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = [
            "id",
            "name",
            "unit_id",
            "is_active",
            "created_at",
            "active_document_count",
        ]
        read_only_fields = ["id", "created_at", "active_document_count"]

    def get_active_document_count(self, obj):
        return obj.active_document_count()
