"""
Utility functions for uploading CSS files to Google Cloud Storage (GCS).

This module provides reusable functions for handling CSS file uploads to GCP,
which can be used by both student and teacher code snippet views.
"""
import uuid
import re
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def sanitize_filename(filename):
    """
    Sanitize a filename for safe storage in GCS.
    Removes or replaces invalid characters.
    
    Args:
        filename: Original filename (e.g., "My Styles.css" or "styles")
    
    Returns:
        Sanitized filename safe for GCS (e.g., "my-styles.css")
    """
    # Remove or replace invalid characters
    # Keep only alphanumeric, dash, underscore, and dot
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '-', filename)
    # Remove multiple consecutive dashes
    sanitized = re.sub(r'-+', '-', sanitized)
    # Remove leading/trailing dashes and dots
    sanitized = sanitized.strip('.-')
    # Ensure it doesn't start with a dot (hidden files)
    if sanitized.startswith('.'):
        sanitized = 'file' + sanitized
    # If empty after sanitization, use default
    if not sanitized:
        sanitized = 'styles'
    # Ensure it ends with .css
    if not sanitized.lower().endswith('.css'):
        sanitized = sanitized + '.css'
    return sanitized.lower()


def upload_css_to_gcp(css_content, title=None):
    """
    Upload CSS content to Google Cloud Storage and return the public URL.
    
    This function:
    1. Creates a unique filename based on title and UUID
    2. Uploads CSS content to GCS at path: css-files/{uuid}-{sanitized-title}.css
    3. Returns the public GCS URL
    
    Args:
        css_content: The CSS code content as a string
        title: Optional title for the CSS file (used in filename)
    
    Returns:
        tuple: (file_url: str, saved_path: str) or (None, None) on error
        
    Example:
        >>> css_code = "h1 { color: blue; }"
        >>> url, path = upload_css_to_gcp(css_code, title="My Styles")
        >>> print(url)  # "https://storage.googleapis.com/bucket-name/css-files/uuid-my-styles.css"
    """
    # Validate inputs
    if not css_content or not css_content.strip():
        logger.warning("Attempted to upload empty CSS content")
        return None, None
    
    # Check if GCS is configured
    if not hasattr(settings, 'GS_BUCKET_NAME') or not settings.GS_BUCKET_NAME:
        logger.error("Google Cloud Storage is not configured. GS_BUCKET_NAME not set.")
        return None, None
    
    try:
        # Generate unique filename
        unique_id = str(uuid.uuid4())
        
        # Sanitize title for filename
        if title and title.strip():
            sanitized_title = sanitize_filename(title.strip())
            # Limit title length to avoid very long filenames
            if len(sanitized_title) > 50:
                sanitized_title = sanitized_title[:50]
            filename = f"{unique_id}-{sanitized_title}"
        else:
            filename = f"{unique_id}-styles"
        
        # Ensure .css extension
        if not filename.endswith('.css'):
            filename = filename + '.css'
        
        # Storage path in GCS
        storage_path = f"css-files/{filename}"
        
        # Create ContentFile from CSS content
        css_file = ContentFile(css_content.encode('utf-8'))
        css_file.name = filename
        
        # Upload to GCS
        saved_path = default_storage.save(storage_path, css_file)
        
        # Get public URL from GCS
        file_url = default_storage.url(saved_path)
        
        # Ensure full URL format for GCS (in case url() doesn't return full URL)
        if not file_url.startswith('http'):
            file_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{saved_path}"
        
        logger.info(f"CSS file uploaded successfully to GCS: {saved_path}")
        logger.info(f"CSS file URL: {file_url}")
        
        return file_url, saved_path
        
    except Exception as e:
        logger.error(f"Error uploading CSS file to GCS: {e}", exc_info=True)
        return None, None


def delete_css_from_gcp(css_file_url):
    """
    Delete a CSS file from Google Cloud Storage given its URL.
    
    Args:
        css_file_url: The GCS URL of the CSS file to delete
    
    Returns:
        bool: True if deleted successfully, False otherwise
    """
    if not css_file_url:
        return False
    
    try:
        # Extract the path from the URL
        # URL format: https://storage.googleapis.com/bucket-name/css-files/uuid-filename.css
        # or: /media/css-files/uuid-filename.css
        if 'storage.googleapis.com' in css_file_url:
            # Extract path after bucket name
            parts = css_file_url.split('/')
            try:
                # Find 'css-files' in the URL and get everything after it
                css_files_index = parts.index('css-files')
                file_path = '/'.join(parts[css_files_index:])
            except ValueError:
                # Fallback: try to extract from end of URL
                file_path = css_file_url.split('/css-files/')[-1]
                if file_path:
                    file_path = f"css-files/{file_path}"
                else:
                    logger.warning(f"Could not extract path from CSS URL: {css_file_url}")
                    return False
        else:
            # Assume it's a relative path
            file_path = css_file_url.lstrip('/')
        
        # Check if file exists before trying to delete
        if default_storage.exists(file_path):
            default_storage.delete(file_path)
            logger.info(f"CSS file deleted from GCS: {file_path}")
            return True
        else:
            logger.warning(f"CSS file not found in GCS: {file_path}")
            return False
            
    except Exception as e:
        logger.error(f"Error deleting CSS file from GCS: {e}", exc_info=True)
        return False

