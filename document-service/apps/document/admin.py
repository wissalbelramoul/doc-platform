"""
Admin configuration for Document Service
"""
from django.contrib import admin
from apps.document.models import Document, DocumentVersion, DocumentHistory


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'owner_id', 'category', 'created_at', 'is_deleted')
    list_filter = ('status', 'category', 'created_at', 'deleted_at')
    search_fields = ('title', 'description', 'keywords')
    readonly_fields = ('id', 'created_at', 'updated_at', 'deleted_at')
    
    fieldsets = (
        ('General', {
            'fields': ('id', 'title', 'description', 'category', 'keywords')
        }),
        ('Metadata', {
            'fields': ('owner_id', 'block_id', 'service_id', 'department_id')
        }),
        ('Status', {
            'fields': ('status', 'current_version')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'deleted_at')
        }),
    )


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ('document', 'version_number', 'file_size', 'mime_type', 'created_at')
    list_filter = ('mime_type', 'created_at')
    search_fields = ('document__title', 'file_path')
    readonly_fields = ('id', 'file_hash', 'created_at')


@admin.register(DocumentHistory)
class DocumentHistoryAdmin(admin.ModelAdmin):
    list_display = ('document', 'user_id', 'action', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('document__title', 'user_id')
    readonly_fields = ('id', 'created_at')
