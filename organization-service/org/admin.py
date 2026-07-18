from django.contrib import admin

from .models import (
    AssignmentRequest,
    DocumentCountProjection,
    EmployeeAssignment,
    OrganizationalResponsibility,
    OrganizationalUnit,
    Service,
)


@admin.register(OrganizationalUnit)
class OrganizationalUnitAdmin(admin.ModelAdmin):
    # Le ModelForm généré par l'admin appelle full_clean() à la sauvegarde :
    # c'est ici (ou via un script appelant full_clean() explicitement) que
    # les règles de OrganizationalUnit.clean() sont réellement appliquées.
    list_display = ("name", "type", "is_active", "depth")
    list_filter = ("type", "is_active")
    search_fields = ("name", "external_id")


@admin.register(OrganizationalResponsibility)
class OrganizationalResponsibilityAdmin(admin.ModelAdmin):
    list_display = ("role", "user_id", "unit", "started_at", "ended_at")
    list_filter = ("role",)
    search_fields = ("user_id",)


@admin.register(EmployeeAssignment)
class EmployeeAssignmentAdmin(admin.ModelAdmin):
    list_display = ("role", "user_id", "unit", "started_at", "ended_at")
    list_filter = ("role", "started_at")
    search_fields = ("user_id",)


@admin.register(AssignmentRequest)
class AssignmentRequestAdmin(admin.ModelAdmin):
    list_display = ("target_user_id", "role", "status", "requester_user_id", "created_at")
    list_filter = ("status", "role")
    search_fields = ("target_user_id", "requester_user_id")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(DocumentCountProjection)
class DocumentCountProjectionAdmin(admin.ModelAdmin):
    list_display = ("service_id", "active_count")
