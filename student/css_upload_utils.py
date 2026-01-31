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

# Try to import GCS client for direct uploads (for overwrite capability)
try:
    from google.cloud import storage
    from google.oauth2 import service_account
    GCS_CLIENT_AVAILABLE = True
except ImportError:
    GCS_CLIENT_AVAILABLE = False
    logger.warning("google-cloud-storage not available, will use default_storage only")


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


def upload_css_to_gcp(css_content, title=None, snippet_id=None):
    """
    Upload CSS content to Google Cloud Storage and return the public URL.
    
    This function:
    1. Creates a unique filename based on snippet_id (if provided) or generates a new UUID
    2. Uploads CSS content to GCS at path: css-files/{snippet_id or uuid}-{sanitized-title}.css
    3. Returns the public GCS URL
    
    When snippet_id is provided, the same filename (and URL) will be used, ensuring
    consistency across updates. For new snippets, snippet_id should be None to generate
    a new UUID.
    
    Args:
        css_content: The CSS code content as a string
        title: Optional title for the CSS file (used in filename)
        snippet_id: Optional UUID of the code snippet. If provided, uses this ID instead
                    of generating a new UUID, ensuring the URL stays consistent across updates.
    
    Returns:
        tuple: (file_url: str, saved_path: str) or (None, None) on error
        
    Example:
        >>> css_code = "h1 { color: blue; }"
        >>> url, path = upload_css_to_gcp(css_code, title="My Styles")
        >>> print(url)  # "https://storage.googleapis.com/bucket-name/css-files/uuid-my-styles.css"
        >>> # For updates, use snippet_id to keep URL consistent:
        >>> url, path = upload_css_to_gcp(css_code, title="My Styles", snippet_id=snippet.id)
    """
    print("=" * 80)
    print("[upload_css_to_gcp] FUNCTION CALLED")
    print(f"[upload_css_to_gcp] title parameter: {title}")
    print(f"[upload_css_to_gcp] snippet_id parameter: {snippet_id}")
    print(f"[upload_css_to_gcp] css_content length: {len(css_content) if css_content else 0} chars")
    
    # Validate inputs
    if not css_content or not css_content.strip():
        print("[upload_css_to_gcp] ERROR: Empty CSS content")
        logger.warning("Attempted to upload empty CSS content")
        return None, None
    
    # Check if GCS is configured
    if not hasattr(settings, 'GS_BUCKET_NAME') or not settings.GS_BUCKET_NAME:
        print("[upload_css_to_gcp] ERROR: GCS not configured")
        logger.error("Google Cloud Storage is not configured. GS_BUCKET_NAME not set.")
        return None, None
    
    try:
        # Use snippet_id if provided (for updates), otherwise generate new UUID (for new snippets)
        if snippet_id:
            unique_id = str(snippet_id)
            print(f"[upload_css_to_gcp] Using snippet_id as UUID: {unique_id}")
        else:
            unique_id = str(uuid.uuid4())
            print(f"[upload_css_to_gcp] Generated new UUID: {unique_id}")
        
        # Sanitize title for filename
        if title and title.strip():
            sanitized_title = sanitize_filename(title.strip())
            # Limit title length to avoid very long filenames
            if len(sanitized_title) > 50:
                sanitized_title = sanitized_title[:50]
            filename = f"{unique_id}-{sanitized_title}"
            print(f"[upload_css_to_gcp] Sanitized title: '{sanitized_title}'")
        else:
            filename = f"{unique_id}-styles"
            print(f"[upload_css_to_gcp] No title provided, using 'styles'")
        
        # Ensure .css extension
        if not filename.endswith('.css'):
            filename = filename + '.css'
        
        print(f"[upload_css_to_gcp] Final filename: {filename}")
        
        # Storage path in GCS
        storage_path = f"css-files/{filename}"
        print(f"[upload_css_to_gcp] Storage path: {storage_path}")
        
        # Create ContentFile from CSS content
        css_file = ContentFile(css_content.encode('utf-8'))
        css_file.name = filename
        
        # For updates (when snippet_id is provided), use GCS client directly to ensure overwrite
        # and set cache-control headers to prevent caching issues
        if snippet_id and GCS_CLIENT_AVAILABLE:
            print(f"[upload_css_to_gcp] Using GCS client directly for overwrite (snippet_id provided)")
            try:
                # Get GCS client
                if hasattr(settings, 'GS_CREDENTIALS') and settings.GS_CREDENTIALS:
                    if isinstance(settings.GS_CREDENTIALS, str):
                        # Path to credentials file
                        client = storage.Client.from_service_account_json(
                            settings.GS_CREDENTIALS,
                            project=settings.GS_PROJECT_ID
                        )
                    else:
                        # Credentials object
                        client = storage.Client(
                            credentials=settings.GS_CREDENTIALS,
                            project=settings.GS_PROJECT_ID
                        )
                else:
                    # Use default credentials
                    client = storage.Client(project=settings.GS_PROJECT_ID)
                
                bucket = client.bucket(settings.GS_BUCKET_NAME)
                blob = bucket.blob(storage_path)
                
                # Set cache-control to prevent caching
                blob.cache_control = 'no-cache, no-store, must-revalidate'
                blob.content_type = 'text/css'
                
                # Upload with overwrite
                css_file.seek(0)  # Reset file pointer
                blob.upload_from_file(css_file, content_type='text/css')
                
                # Make it publicly readable
                blob.make_public()
                
                saved_path = storage_path
                file_url = blob.public_url
                print(f"[upload_css_to_gcp] GCS client upload successful")
                print(f"[upload_css_to_gcp] Cache-control set to: no-cache, no-store, must-revalidate")
            except Exception as e:
                print(f"[upload_css_to_gcp] WARNING: GCS client upload failed: {e}, falling back to default_storage")
                logger.warning(f"GCS client upload failed, using default_storage: {e}")
                # Fall back to default_storage
                css_file.seek(0)
                saved_path = default_storage.save(storage_path, css_file)
                file_url = default_storage.url(saved_path)
                if not file_url.startswith('http'):
                    file_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{saved_path}"
        else:
            # For new files or if GCS client not available, use default_storage
            print(f"[upload_css_to_gcp] Using default_storage.save()")
            saved_path = default_storage.save(storage_path, css_file)
            print(f"[upload_css_to_gcp] Saved path returned: {saved_path}")
            
            # Get public URL from GCS
            file_url = default_storage.url(saved_path)
            print(f"[upload_css_to_gcp] Initial file_url from default_storage.url(): {file_url}")
            
            # Ensure full URL format for GCS (in case url() doesn't return full URL)
            if not file_url.startswith('http'):
                file_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{saved_path}"
                print(f"[upload_css_to_gcp] Constructed full URL: {file_url}")
        
        print(f"[upload_css_to_gcp] FINAL file_url: {file_url}")
        print(f"[upload_css_to_gcp] FINAL saved_path: {saved_path}")
        print("=" * 80)
        
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
    print("=" * 80)
    print("[delete_css_from_gcp] FUNCTION CALLED")
    print(f"[delete_css_from_gcp] css_file_url parameter: {css_file_url}")
    
    if not css_file_url:
        print("[delete_css_from_gcp] ERROR: No css_file_url provided")
        return False
    
    try:
        # Extract the path from the URL
        # URL format: https://storage.googleapis.com/bucket-name/css-files/uuid-filename.css
        # or: /media/css-files/uuid-filename.css
        if 'storage.googleapis.com' in css_file_url:
            print("[delete_css_from_gcp] URL contains 'storage.googleapis.com'")
            # Extract path after bucket name
            parts = css_file_url.split('/')
            print(f"[delete_css_from_gcp] URL parts: {parts}")
            try:
                # Find 'css-files' in the URL and get everything after it
                css_files_index = parts.index('css-files')
                file_path = '/'.join(parts[css_files_index:])
                print(f"[delete_css_from_gcp] Found 'css-files' at index {css_files_index}")
            except ValueError:
                print("[delete_css_from_gcp] 'css-files' not found in URL parts, using fallback")
                # Fallback: try to extract from end of URL
                file_path = css_file_url.split('/css-files/')[-1]
                if file_path:
                    file_path = f"css-files/{file_path}"
                else:
                    print(f"[delete_css_from_gcp] ERROR: Could not extract path from CSS URL")
                    logger.warning(f"Could not extract path from CSS URL: {css_file_url}")
                    return False
        else:
            print("[delete_css_from_gcp] URL does not contain 'storage.googleapis.com', treating as relative path")
            # Assume it's a relative path
            file_path = css_file_url.lstrip('/')
        
        print(f"[delete_css_from_gcp] Extracted file_path: {file_path}")
        
        # Check if file exists before trying to delete
        file_exists = default_storage.exists(file_path)
        print(f"[delete_css_from_gcp] File exists check: {file_exists}")
        
        if file_exists:
            default_storage.delete(file_path)
            print(f"[delete_css_from_gcp] SUCCESS: Deleted file at {file_path}")
            logger.info(f"CSS file deleted from GCS: {file_path}")
            print("=" * 80)
            return True
        else:
            print(f"[delete_css_from_gcp] WARNING: File not found in GCS: {file_path}")
            logger.warning(f"CSS file not found in GCS: {file_path}")
            print("=" * 80)
            return False
            
    except Exception as e:
        print(f"[delete_css_from_gcp] EXCEPTION: {e}")
        logger.error(f"Error deleting CSS file from GCS: {e}", exc_info=True)
        print("=" * 80)
        return False

