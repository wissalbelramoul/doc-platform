"""
Models for Document Service
"""
import uuid
import hashlib
from django.db import models
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.contrib.auth.models import User


class Document(models.Model):
    """Main document model"""
    
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('pending', 'En attente'),
        ('validated', 'Validé'),
        ('rejected', 'Refusé'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100)
    keywords = models.TextField(blank=True, help_text="Comma-separated tags")
    
    # Foreign keys
    owner_id = models.IntegerField()  # Reference to User service
    block_id = models.IntegerField(blank=True, null=True)
    service_id = models.IntegerField(blank=True, null=True)
    department_id = models.IntegerField(blank=True, null=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    current_version = models.OneToOneField(
        'DocumentVersion', 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='current_document'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)  # Soft delete
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner_id']),
            models.Index(fields=['status']),
            models.Index(fields=['deleted_at']),
            models.Index(fields=['category']),
        ]
    
    def __str__(self):
        return self.title
    
    def soft_delete(self):
        """Soft delete the document"""
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore a soft-deleted document"""
        self.deleted_at = None
        self.save()
    
    @property
    def is_deleted(self):
        return self.deleted_at is not None


class DocumentVersion(models.Model):
    """Version management for documents"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document, 
        on_delete=models.CASCADE, 
        related_name='versions'
    )
    
    # File information
    version_number = models.IntegerField()
    file_path = models.CharField(max_length=500)  # S3/MinIO path or local path
    file_size = models.BigIntegerField()  # in bytes
    mime_type = models.CharField(max_length=100)
    file_hash = models.CharField(max_length=64, unique=True)  # SHA-256
    
    # Metadata
    author_id = models.IntegerField()  # Reference to User service
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-version_number']
        indexes = [
            models.Index(fields=['document']),
            models.Index(fields=['file_hash']),
        ]
    
    def __str__(self):
        return f"{self.document.title} v{self.version_number}"
    
    @staticmethod
    def calculate_file_hash(file_obj):
        """Calculate SHA-256 hash of file"""
        hash_obj = hashlib.sha256()
        for chunk in file_obj.chunks():
            hash_obj.update(chunk)
        return hash_obj.hexdigest()


class DocumentHistory(models.Model):
    """Audit trail for document actions"""
    
    ACTION_CHOICES = [
        ('upload', 'Upload'),
        ('modification', 'Modification'),
        ('deletion', 'Suppression'),
        ('download', 'Téléchargement'),
        ('view', 'Consultation'),
        ('validation', 'Validation'),
        ('rejection', 'Rejet'),
        ('restore', 'Restauration'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document, 
        on_delete=models.CASCADE, 
        related_name='history'
    )
    
    user_id = models.IntegerField()  # Reference to User service
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    details = models.JSONField(default=dict, blank=True)  # Additional details
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Document Histories"
        indexes = [
            models.Index(fields=['document']),
            models.Index(fields=['user_id']),
            models.Index(fields=['action']),
        ]
    
    def __str__(self):
        return f"{self.action} on {self.document.title} by user {self.user_id}"
