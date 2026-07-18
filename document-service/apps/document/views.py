"""
Views and ViewSets for Document Service
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend

from apps.document.models import Document, DocumentVersion, DocumentHistory
from apps.document.serializers import (
    DocumentListSerializer,
    DocumentDetailSerializer,
    DocumentCreateUpdateSerializer,
    DocumentVersionSerializer,
    DocumentHistorySerializer,
)
from apps.document.permissions import (
    IsDocumentOwnerOrBlockManager,
    CanViewDocument,
    CanDeleteDocument,
)
from apps.document.utils import publish_event, generate_signed_url


class DocumentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Document CRUD operations
    
    Endpoints:
    - POST   /documents/                      → Create new document
    - GET    /documents/                      → List documents (with filters)
    - GET    /documents/{id}/                 → Get document details
    - PUT    /documents/{id}/                 → Update document
    - DELETE /documents/{id}/                 → Delete document (soft delete)
    - GET    /documents/{id}/versions/        → List versions
    - POST   /documents/{id}/restore/         → Restore soft-deleted document
    - GET    /documents/{id}/download/        → Download current version
    - GET    /documents/{id}/history/         → Get audit trail
    """
    
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'category', 'block_id', 'service_id', 'department_id']
    search_fields = ['title', 'description', 'keywords']
    ordering_fields = ['created_at', 'updated_at', 'title']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create' or self.action == 'update' or self.action == 'partial_update':
            return DocumentCreateUpdateSerializer
        elif self.action == 'list':
            return DocumentListSerializer
        return DocumentDetailSerializer
    
    def get_queryset(self):
        """Filter documents based on user permissions"""
        # Get all non-deleted documents by default
        queryset = Document.objects.filter(deleted_at__isnull=True).select_related('current_version')
        
        # Filter by owner or block/service/department
        user_id = self.request.query_params.get('user_id', None)
        if user_id:
            queryset = queryset.filter(owner_id=user_id)
        
        # In a real system, this would check actual user permissions from auth service
        # For now, we allow users to see all non-deleted documents
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create new document"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save()
        
        # Publish DocumentCreated event
        publish_event('document.created', {
            'document_id': str(document.id),
            'title': document.title,
            'owner_id': document.owner_id,
            'status': document.status,
            'timestamp': timezone.now().isoformat(),
        })
        
        # Log action
        DocumentHistory.objects.create(
            document=document,
            user_id=request.data.get('owner_id', 0),
            action='upload',
            details={'filename': request.data.get('file', {}).name if 'file' in request.data else None}
        )
        
        return Response(
            DocumentDetailSerializer(document).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, *args, **kwargs):
        """Update document"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        document = serializer.save()
        
        # Publish DocumentModified event
        publish_event('document.modified', {
            'document_id': str(document.id),
            'title': document.title,
            'status': document.status,
            'timestamp': timezone.now().isoformat(),
        })
        
        # Log action
        DocumentHistory.objects.create(
            document=document,
            user_id=request.data.get('owner_id', 0),
            action='modification',
            details={'fields': list(request.data.keys())}
        )
        
        return Response(DocumentDetailSerializer(document).data)
    
    def destroy(self, request, *args, **kwargs):
        """Soft delete document"""
        instance = self.get_object()
        instance.soft_delete()
        
        # Publish DocumentDeleted event
        publish_event('document.deleted', {
            'document_id': str(instance.id),
            'title': instance.title,
            'timestamp': timezone.now().isoformat(),
        })
        
        # Log action
        DocumentHistory.objects.create(
            document=instance,
            user_id=request.user.id,
            action='deletion',
            details={}
        )
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore a soft-deleted document"""
        document = self.get_object()
        
        if not document.is_deleted:
            return Response(
                {'detail': 'Document is not deleted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        document.restore()
        
        # Publish DocumentRestored event
        publish_event('document.restored', {
            'document_id': str(document.id),
            'title': document.title,
            'timestamp': timezone.now().isoformat(),
        })
        
        # Log action
        DocumentHistory.objects.create(
            document=document,
            user_id=request.user.id,
            action='restore',
            details={}
        )
        
        return Response(DocumentDetailSerializer(document).data)
    
    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        """List all versions of a document"""
        document = self.get_object()
        versions = document.versions.all()
        serializer = DocumentVersionSerializer(versions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def restore_version(self, request, pk=None):
        """Restore a previous version of document"""
        document = self.get_object()
        version_id = request.data.get('version_id')
        
        try:
            version = DocumentVersion.objects.get(id=version_id, document=document)
        except DocumentVersion.DoesNotExist:
            return Response(
                {'detail': 'Version not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create new version from old one (copy)
        last_version = document.versions.all().order_by('-version_number').first()
        new_version_number = (last_version.version_number + 1) if last_version else 1
        
        new_version = DocumentVersion.objects.create(
            document=document,
            version_number=new_version_number,
            file_path=version.file_path,
            file_size=version.file_size,
            mime_type=version.mime_type,
            file_hash=version.file_hash,
            author_id=request.user.id,
            comment=f"Restored from version {version.version_number}"
        )
        
        document.current_version = new_version
        document.status = 'pending'
        document.save()
        
        # Publish event
        publish_event('document.version_restored', {
            'document_id': str(document.id),
            'from_version': version.version_number,
            'to_version': new_version_number,
            'timestamp': timezone.now().isoformat(),
        })
        
        # Log action
        DocumentHistory.objects.create(
            document=document,
            user_id=request.user.id,
            action='modification',
            details={'restored_from_version': version.version_number}
        )
        
        return Response(DocumentVersionSerializer(new_version).data)
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download current version of document"""
        document = self.get_object()
        
        if not document.current_version:
            return Response(
                {'detail': 'No version available'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        version = document.current_version
        
        # Generate signed URL (expires in 15 minutes)
        signed_url = generate_signed_url(version.file_path, expires_in=900)
        
        # Log download action
        DocumentHistory.objects.create(
            document=document,
            user_id=request.user.id,
            action='download',
            details={'version': version.version_number}
        )
        
        return Response({
            'download_url': signed_url,
            'filename': version.file_path.split('/')[-1],
            'file_size': version.file_size,
            'expires_in': 900
        })
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Get audit trail for document"""
        document = self.get_object()
        history = document.history.all()
        
        # Pagination
        page_size = request.query_params.get('page_size', 20)
        page = request.query_params.get('page', 1)
        
        try:
            start = (int(page) - 1) * int(page_size)
            end = start + int(page_size)
            history = history[start:end]
        except (ValueError, TypeError):
            pass
        
        serializer = DocumentHistorySerializer(history, many=True)
        return Response(serializer.data)


class DocumentVersionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for document versions
    
    Endpoints:
    - GET /versions/           → List all versions
    - GET /versions/{id}/      → Get specific version
    """
    
    queryset = DocumentVersion.objects.all()
    serializer_class = DocumentVersionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['document']
    ordering = ['-created_at']
