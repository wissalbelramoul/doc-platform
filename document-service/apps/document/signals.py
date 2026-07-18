"""
Signal handlers for Document Service
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.conf import settings
from apps.document.models import Document, DocumentHistory
from apps.document.utils import publish_event
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Document)
def document_status_changed(sender, instance, created, **kwargs):
    """Handle document status changes"""
    if created:
        # New document created - already handled in view
        pass
    else:
        # Document updated
        pass


# Celery task for soft delete cleanup
def cleanup_soft_deleted_documents():
    """
    Periodic task to permanently delete soft-deleted documents after retention period
    Should be run by Celery Beat scheduler
    """
    from django.utils import timezone
    from datetime import timedelta
    
    retention_days = getattr(settings, 'SOFT_DELETE_RETENTION_DAYS', 90)
    cutoff_date = timezone.now() - timedelta(days=retention_days)
    
    deleted_docs = Document.objects.filter(
        deleted_at__lte=cutoff_date,
        deleted_at__isnull=False
    )
    
    count = deleted_docs.count()
    
    for doc in deleted_docs:
        # Publish event before deletion
        publish_event('document.permanently_deleted', {
            'document_id': str(doc.id),
            'title': doc.title,
            'timestamp': timezone.now().isoformat(),
        })
        
        # Delete versions and history
        doc.versions.all().delete()
        doc.history.all().delete()
        doc.delete()
    
    logger.info(f"Permanently deleted {count} documents")
    
    return count
