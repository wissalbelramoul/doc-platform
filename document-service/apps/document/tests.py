"""
Tests for Document Service
"""
import json
from django.test import TestCase, Client
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from apps.document.models import Document, DocumentVersion, DocumentHistory


class DocumentModelTests(TestCase):
    """Test Document model"""
    
    def setUp(self):
        self.document = Document.objects.create(
            title="Test Document",
            description="Test description",
            category="Test",
            owner_id=1,
            status='pending'
        )
    
    def test_document_creation(self):
        self.assertEqual(self.document.title, "Test Document")
        self.assertEqual(self.document.status, "pending")
        self.assertFalse(self.document.is_deleted)
    
    def test_soft_delete(self):
        self.document.soft_delete()
        self.assertTrue(self.document.is_deleted)
        self.assertIsNotNone(self.document.deleted_at)
    
    def test_soft_delete_restore(self):
        self.document.soft_delete()
        self.document.restore()
        self.assertFalse(self.document.is_deleted)
        self.assertIsNone(self.document.deleted_at)


class DocumentVersionTests(TestCase):
    """Test DocumentVersion model"""
    
    def setUp(self):
        self.document = Document.objects.create(
            title="Test Document",
            owner_id=1,
            status='pending'
        )
    
    def test_version_creation(self):
        version = DocumentVersion.objects.create(
            document=self.document,
            version_number=1,
            file_path="test.pdf",
            file_size=1024,
            mime_type="application/pdf",
            file_hash="abc123",
            author_id=1
        )
        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.document, self.document)


class DocumentHistoryTests(TestCase):
    """Test DocumentHistory model"""
    
    def setUp(self):
        self.document = Document.objects.create(
            title="Test Document",
            owner_id=1,
            status='pending'
        )
    
    def test_history_creation(self):
        history = DocumentHistory.objects.create(
            document=self.document,
            user_id=1,
            action='upload',
            details={'filename': 'test.pdf'}
        )
        self.assertEqual(history.action, 'upload')
        self.assertEqual(history.user_id, 1)


class DocumentAPITests(APITestCase):
    """Test Document API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        self.document_data = {
            'title': 'Test Document',
            'description': 'Test description',
            'category': 'Test',
            'owner_id': 1,
        }
    
    def test_list_documents(self):
        # Create test documents
        Document.objects.create(**self.document_data)
        
        response = self.client.get('/api/documents/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)  # Without auth
    
    def test_document_filtering(self):
        # Create documents with different statuses
        Document.objects.create(**self.document_data, status='pending')
        Document.objects.create(**self.document_data, status='validated')
        
        # Would test filtering after authentication is implemented
        pass
