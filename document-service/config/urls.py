"""
URL Configuration for Document Service
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.document.views import DocumentViewSet, DocumentVersionViewSet

router = DefaultRouter()
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'versions', DocumentVersionViewSet, basename='version')

urlpatterns = [
    path('api/', include(router.urls)),
]
