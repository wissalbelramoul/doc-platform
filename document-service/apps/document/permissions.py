"""
Custom permission classes for Document Service
"""
from rest_framework import permissions


class IsDocumentOwnerOrBlockManager(permissions.BasePermission):
    """
    Permission to check if user is document owner or block manager
    """
    message = "You don't have permission to access this document"
    
    def has_object_permission(self, request, view, obj):
        # Document owner can always access
        if obj.owner_id == request.user.id:
            return True
        
        # Block manager can access documents in their block
        # In real implementation, would check user's roles via auth service
        return False


class CanViewDocument(permissions.BasePermission):
    """
    Permission to view document
    """
    message = "You don't have permission to view this document"
    
    def has_object_permission(self, request, view, obj):
        # Check if user can view (would query auth service)
        return True  # Placeholder


class CanDeleteDocument(permissions.BasePermission):
    """
    Permission to delete document
    """
    message = "You don't have permission to delete this document"
    
    def has_object_permission(self, request, view, obj):
        # Only owner or admin can delete
        if obj.owner_id == request.user.id:
            return True
        return False
