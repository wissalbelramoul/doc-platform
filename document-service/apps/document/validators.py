"""
Validators for Document Service
"""
import os
from django.core.exceptions import ValidationError
from django.conf import settings


def validate_document_file(uploaded_file):
    """
    Comprehensive file validation for documents
    
    1. Check extension (whitelist)
    2. Check size
    3. Verify MIME type
    4. Scan for malicious content in code/HTML files
    """
    if not uploaded_file:
        raise ValidationError("No file provided")
    
    # Get extension
    ext = os.path.splitext(uploaded_file.name)[1].lower().lstrip('.')
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise ValidationError(f"Extension .{ext} non autorisée. Extensions acceptées: {', '.join(settings.ALLOWED_EXTENSIONS)}")
    
    # Check size
    max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 20 * 1024 * 1024)
    if uploaded_file.size > max_size:
        raise ValidationError(f"Fichier trop volumineux. Taille max: {max_size / 1024 / 1024:.0f} Mo")
    
    # Check MIME type
    mime_type = uploaded_file.content_type
    if mime_type not in settings.ALLOWED_MIME_TYPES:
        # Allow text/* for code files
        if not mime_type.startswith('text/'):
            raise ValidationError(f"Type MIME {mime_type} non autorisé")
    
    # Additional checks for potentially dangerous file types
    dangerous_extensions = {'html', 'js', 'svg', 'xml'}
    if ext in dangerous_extensions:
        # Read first chunk to scan for malicious content
        uploaded_file.seek(0)
        try:
            content_chunk = uploaded_file.read(2048).decode('utf-8', errors='ignore').lower()
            uploaded_file.seek(0)
            
            suspicious_patterns = [
                '<script', 'javascript:', 'onerror=', 'onload=', 
                'onclick=', 'onmouseover=', 'onfocus=', 'eval(',
                'exec(', 'system('
            ]
            
            if any(pattern in content_chunk for pattern in suspicious_patterns):
                raise ValidationError(
                    f"Contenu potentiellement dangereux détecté dans le fichier .{ext}"
                )
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            # If we can't read the file, still allow it (might be binary-like text)
            pass
    
    return True
