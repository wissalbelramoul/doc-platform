"""
Serializers for Document Service
"""
from rest_framework import serializers
from apps.document.models import Document, DocumentVersion, DocumentHistory
from apps.document.validators import validate_document_file


class DocumentVersionSerializer(serializers.ModelSerializer):
    """Serializer for document versions"""
    
    class Meta:
        model = DocumentVersion
        fields = [
            'id', 'document', 'version_number', 'file_path', 'file_size',
            'mime_type', 'file_hash', 'author_id', 'comment', 'created_at'
        ]
        read_only_fields = ['id', 'version_number', 'file_path', 'file_size', 
                           'mime_type', 'file_hash', 'created_at']


class DocumentDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for documents with versions"""
    
    versions = DocumentVersionSerializer(many=True, read_only=True)
    current_version = DocumentVersionSerializer(read_only=True)
    keywords_list = serializers.SerializerMethodField()
    
    class Meta:
        model = Document
        fields = [
            'id', 'title', 'description', 'category', 'keywords', 'keywords_list',
            'owner_id', 'block_id', 'service_id', 'department_id', 'status',
            'current_version', 'versions', 'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_deleted', 'created_at', 'updated_at']
    
    def get_keywords_list(self, obj):
        """Convert comma-separated keywords to list"""
        if obj.keywords:
            return [kw.strip() for kw in obj.keywords.split(',')]
        return []


class DocumentListSerializer(serializers.ModelSerializer):
    """Simple serializer for document lists"""
    
    class Meta:
        model = Document
        fields = [
            'id', 'title', 'category', 'status', 'owner_id',
            'is_deleted', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_deleted', 'created_at', 'updated_at']


class DocumentCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating documents"""
    
    file = serializers.FileField(write_only=True, required=False, validators=[validate_document_file])
    version_comment = serializers.CharField(write_only=True, required=False, allow_blank=True)
    keywords_list = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        help_text="List of keywords/tags"
    )
    
    class Meta:
        model = Document
        fields = [
            'title', 'description', 'category', 'keywords_list',
            'owner_id', 'block_id', 'service_id', 'department_id',
            'file', 'version_comment'
        ]
    
    def create(self, validated_data):
        """Create document with initial version"""
        file = validated_data.pop('file', None)
        version_comment = validated_data.pop('version_comment', '')
        keywords_list = validated_data.pop('keywords_list', [])
        
        # Convert keywords list to comma-separated string
        if keywords_list:
            validated_data['keywords'] = ','.join(keywords_list)
        
        document = Document.objects.create(**validated_data)
        
        # Create initial version if file provided
        if file:
            self._create_version(document, file, version_comment, validated_data.get('owner_id'))
        
        return document
    
    def update(self, instance, validated_data):
        """Update document"""
        file = validated_data.pop('file', None)
        version_comment = validated_data.pop('version_comment', '')
        keywords_list = validated_data.pop('keywords_list', None)
        
        # Update basic fields
        for attr, value in validated_data.items():
            if value is not None:
                if attr == 'keywords_list':
                    setattr(instance, 'keywords', ','.join(value))
                else:
                    setattr(instance, attr, value)
        
        # Convert keywords list if provided
        if keywords_list:
            instance.keywords = ','.join(keywords_list)
        
        instance.save()
        
        # Create new version if file provided
        if file:
            # Reset status to pending if file changed
            instance.status = 'pending'
            instance.save()
            self._create_version(instance, file, version_comment, instance.owner_id)
        
        return instance
    
    @staticmethod
    def _create_version(document, file, comment, author_id):
        """Helper method to create document version"""
        # Calculate file hash
        file_hash = DocumentVersion.calculate_file_hash(file)
        
        # Get version number
        last_version = document.versions.all().order_by('-version_number').first()
        version_number = (last_version.version_number + 1) if last_version else 1
        
        # Create version
        version = DocumentVersion.objects.create(
            document=document,
            version_number=version_number,
            file_path=file.name,  # In production, would be S3/MinIO path
            file_size=file.size,
            mime_type=file.content_type,
            file_hash=file_hash,
            author_id=author_id,
            comment=comment
        )
        
        # Update current version
        document.current_version = version
        document.save()
        
        return version


class DocumentHistorySerializer(serializers.ModelSerializer):
    """Serializer for document history/audit trail"""
    
    class Meta:
        model = DocumentHistory
        fields = [
            'id', 'document', 'user_id', 'action', 'details', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
