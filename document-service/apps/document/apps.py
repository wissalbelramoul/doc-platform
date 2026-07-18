"""
App configuration for Document Service
"""
from django.apps import AppConfig


class DocumentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.document'
    verbose_name = 'Document Management'
    
    def ready(self):
        """Register signal handlers"""
        import apps.document.signals  # noqa
