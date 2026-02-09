"""
File Upload Utility Service
Shared utility for handling file uploads to Google Cloud Storage.
Used by both teacher and student views to ensure consistent behavior.
"""
import logging
import uuid
import re
from pathlib import Path
from urllib.parse import urlparse, unquote
from PIL import Image
from io import BytesIO
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings

logger = logging.getLogger(__name__)


class FileUploadService:
    """
    Utility service for uploading files to Google Cloud Storage.
    Handles images, videos, audio, documents, and other file types.
    For images, compresses and generates thumbnails. For other files, uploads as-is.
    """
    
    @staticmethod
    def detect_file_type(mime_type: str, file_extension: str) -> str:
        """Detect file type from MIME type and extension."""
        if mime_type.startswith('image/'):
            return 'image'
        elif mime_type.startswith('video/'):
            return 'video'
        elif mime_type.startswith('audio/'):
            return 'audio'
        elif mime_type == 'application/pdf' or file_extension == 'pdf':
            return 'document'
        elif 'document' in mime_type or 'word' in mime_type or 'excel' in mime_type or 'powerpoint' in mime_type:
            return 'document'
        elif file_extension in ['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'rtf']:
            return 'document'
        else:
            return 'other'
    
    @staticmethod
    def get_max_size(file_type: str) -> int:
        """Get maximum file size in bytes based on file type."""
        size_limits = {
            'image': 10 * 1024 * 1024,  # 10MB
            'video': 500 * 1024 * 1024,  # 500MB
            'audio': 100 * 1024 * 1024,  # 100MB
            'document': 50 * 1024 * 1024,  # 50MB
            'other': 50 * 1024 * 1024,  # 50MB
        }
        return size_limits.get(file_type, 50 * 1024 * 1024)
    
    @staticmethod
    def handle_image_upload(uploaded_file, storage_path: str, original_filename: str, file_extension: str, mime_type: str) -> dict:
        """
        Handle image upload with compression and thumbnail generation.
        
        Returns:
            dict: File metadata including file_url, thumbnail_url, file_size, etc.
        
        Raises:
            ValueError: If image extension is not allowed or processing fails
            Exception: If upload to GCS fails
        """
        # Validate image extension
        allowed_extensions = ['jpg', 'jpeg', 'png', 'webp', 'gif']
        if file_extension not in allowed_extensions:
            raise ValueError(f'Image extension "{file_extension}" not allowed. Allowed extensions: {", ".join(allowed_extensions)}')
        
        try:
            # Process image with Pillow
            img = Image.open(uploaded_file)
            
            # Convert RGBA/LA/P to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparent images
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize full image to max 1920x1920 (maintains aspect ratio)
            max_size_full = (1920, 1920)
            img.thumbnail(max_size_full, Image.Resampling.LANCZOS)
            
            # Compress and save full image
            full_output = BytesIO()
            img.save(
                full_output,
                format='JPEG',
                quality=85,
                optimize=True,
                progressive=True
            )
            full_output.seek(0)
            
            # Generate thumbnail (400x400)
            img_thumb = img.copy()
            img_thumb.thumbnail((400, 400), Image.Resampling.LANCZOS)
            
            # Compress and save thumbnail
            thumb_output = BytesIO()
            img_thumb.save(
                thumb_output,
                format='JPEG',
                quality=85,
                optimize=True,
                progressive=True
            )
            thumb_output.seek(0)
            
            # Generate unique filenames
            unique_id = uuid.uuid4()
            base_name = original_filename.rsplit('.', 1)[0] if '.' in original_filename else 'image'
            # Sanitize base name
            base_name = ''.join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).strip()[:50]
            
            full_filename = f"{unique_id}-{base_name}.jpg"
            thumb_filename = f"{unique_id}-{base_name}-thumb.jpg"
            
            full_storage_path = f"{storage_path}/images/{full_filename}"
            thumb_storage_path = f"{storage_path}/images/thumbnails/{thumb_filename}"
            
            # Upload full image to GCS
            full_file = ContentFile(full_output.getvalue())
            saved_full_path = default_storage.save(full_storage_path, full_file)
            full_url = default_storage.url(saved_full_path)
            if not full_url.startswith('http'):
                full_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{saved_full_path}"
            
            # Upload thumbnail to GCS
            thumb_file = ContentFile(thumb_output.getvalue())
            saved_thumb_path = default_storage.save(thumb_storage_path, thumb_file)
            thumb_url = default_storage.url(saved_thumb_path)
            if not thumb_url.startswith('http'):
                thumb_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{saved_thumb_path}"
            
            # Get compressed file sizes
            full_size = len(full_output.getvalue())
            
            logger.info(f"Image uploaded successfully: {saved_full_path}, thumbnail: {saved_thumb_path}")
            
            # Return file metadata
            return {
                'file_url': full_url,
                'thumbnail_url': thumb_url,
                'file_size': full_size,
                'file_size_mb': round(full_size / (1024 * 1024), 2),
                'file_extension': 'jpg',
                'mime_type': 'image/jpeg',
                'file_type': 'image',
                'original_filename': original_filename,
            }
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise Exception(f'Failed to process image: {str(e)}')
    
    @staticmethod
    def handle_other_file_upload(uploaded_file, storage_path: str, original_filename: str, file_extension: str, mime_type: str, file_type: str) -> dict:
        """
        Handle non-image file upload (videos, audio, documents, etc.).
        
        Returns:
            dict: File metadata including file_url, file_size, etc.
        
        Raises:
            Exception: If upload to GCS fails
        """
        # Generate unique filename
        unique_id = uuid.uuid4()
        # Sanitize filename
        safe_filename = ''.join(c for c in original_filename if c.isalnum() or c in (' ', '-', '_', '.')).strip()[:100]
        unique_filename = f"{unique_id}-{safe_filename}"
        
        # Organize by file type in storage
        type_folder_map = {
            'video': 'videos',
            'audio': 'audio',
            'document': 'documents',
            'other': 'other'
        }
        type_folder = type_folder_map.get(file_type, 'other')
        
        file_storage_path = f"{storage_path}/{type_folder}/{unique_filename}"
        
        try:
            # Upload file to GCS
            saved_path = default_storage.save(file_storage_path, uploaded_file)
            
            # Get file URL from GCS
            file_url = default_storage.url(saved_path)
            # Ensure full URL format for GCS
            if not file_url.startswith('http'):
                file_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{saved_path}"
            
            logger.info(f"File uploaded successfully: {saved_path}")
            
            # Return file metadata
            return {
                'file_url': file_url,
                'file_size': uploaded_file.size,
                'file_size_mb': round(uploaded_file.size / (1024 * 1024), 2),
                'file_extension': file_extension,
                'mime_type': mime_type,
                'file_type': file_type,
                'original_filename': original_filename,
            }
            
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise Exception(f'Failed to upload file: {str(e)}')
    
    @staticmethod
    def upload_file(uploaded_file, storage_path: str = 'files') -> dict:
        """
        Main entry point for file upload.
        Handles validation, file type detection, and uploads to GCS.
        
        Args:
            uploaded_file: Django UploadedFile object
            storage_path: Optional storage path in GCS (defaults to 'files')
                         Must be alphanumeric with underscores/hyphens only
        
        Returns:
            dict: File metadata including:
                - file_url: GCS URL for the uploaded file
                - file_size: Size in bytes
                - file_size_mb: Size in MB
                - file_extension: File extension
                - mime_type: MIME type
                - file_type: Detected file type (image, video, audio, document, other)
                - original_filename: Original filename
                - thumbnail_url: GCS URL for thumbnail (only for images)
        
        Raises:
            ValueError: If file validation fails
            Exception: If upload or processing fails
        """
        # Check if GCS is configured
        if not hasattr(settings, 'GS_BUCKET_NAME') or not settings.GS_BUCKET_NAME:
            raise Exception('Google Cloud Storage is not configured. Please set GCS_BUCKET_NAME and GCS_PROJECT_ID environment variables.')
        
        # Validate storage path to prevent path traversal attacks (only alphanumeric, underscore, hyphen)
        if not re.match(r'^[a-zA-Z0-9_-]+$', storage_path):
            storage_path = 'files'  # Fallback to default if invalid
        
        # Get file metadata
        original_filename = uploaded_file.name
        file_extension = original_filename.split('.')[-1].lower() if '.' in original_filename else ''
        mime_type = uploaded_file.content_type or 'application/octet-stream'
        
        # Detect file type
        file_type = FileUploadService.detect_file_type(mime_type, file_extension)
        
        # Get size limits based on file type
        max_size = FileUploadService.get_max_size(file_type)
        
        # Validate file size
        if uploaded_file.size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            file_size_mb = round(uploaded_file.size / (1024 * 1024), 2)
            raise ValueError(f'File size ({file_size_mb}MB) exceeds maximum allowed size of {max_size_mb}MB')
        
        # Process based on file type
        if file_type == 'image':
            return FileUploadService.handle_image_upload(
                uploaded_file, storage_path, original_filename, file_extension, mime_type
            )
        else:
            return FileUploadService.handle_other_file_upload(
                uploaded_file, storage_path, original_filename, file_extension, mime_type, file_type
            )
    
    @staticmethod
    def delete_file(file_url: str) -> dict:
        """
        Delete a file from GCS by URL.
        For images, also deletes the associated thumbnail.
        
        Args:
            file_url: GCS URL of the file to delete
        
        Returns:
            dict: Result with 'main_deleted' and 'thumb_deleted' booleans
        
        Raises:
            Exception: If deletion fails
        """
        # Check if GCS is configured
        if not hasattr(settings, 'GS_BUCKET_NAME') or not settings.GS_BUCKET_NAME:
            raise Exception('Google Cloud Storage is not configured')
        
        # Extract file path from GCS URL
        # URL format: https://storage.googleapis.com/BUCKET_NAME/path/to/file
        try:
            parsed_url = urlparse(file_url)
            # Remove leading slash and bucket name from path
            path_parts = parsed_url.path.strip('/').split('/', 1)
            if len(path_parts) > 1:
                file_path = path_parts[1]  # Get path after bucket name
                file_path = unquote(file_path)
            else:
                file_path = parsed_url.path.strip('/')
                file_path = unquote(file_path)
            
            logger.info(f"🗑️ Deleting file from GCS: {file_path} (from URL: {file_url})")
            
            main_deleted = False
            thumb_deleted = False
            
            # Delete main file
            if default_storage.exists(file_path):
                try:
                    default_storage.delete(file_path)
                    main_deleted = True
                    logger.info(f"✅ Deleted file from GCS: {file_path}")
                except Exception as e:
                    logger.error(f"❌ Failed to delete file {file_path}: {e}")
                    raise Exception(f'Failed to delete file: {str(e)}')
            
            # If it's an image, try to delete thumbnail
            # Check if file path suggests it's an image (ends with .jpg and is in images folder)
            if file_path.endswith('.jpg') and ('images' in file_path or 'image' in file_path.lower()):
                try:
                    path_obj = Path(file_path)
                    filename = path_obj.name  # e.g., "abc123-image.jpg"
                    directory = path_obj.parent  # e.g., "assignment_files/images"
                    
                    # Extract UUID and base name from filename
                    if '-' in filename and filename.endswith('.jpg'):
                        name_without_ext = filename[:-4]
                        parts = name_without_ext.rsplit('-', 1)
                        if len(parts) == 2:
                            uuid_part = parts[0]
                            base_name = parts[1]
                            
                            # Construct thumbnail filename
                            thumb_filename = f"{uuid_part}-{base_name}-thumb.jpg"
                            
                            # Determine thumbnail directory
                            if str(directory).endswith('/images') or 'images' in str(directory):
                                thumb_dir = directory / 'thumbnails'
                            else:
                                thumb_dir = directory / 'thumbnails'
                            
                            thumb_path = str(thumb_dir / thumb_filename)
                            
                            # Delete thumbnail
                            if default_storage.exists(thumb_path):
                                try:
                                    default_storage.delete(thumb_path)
                                    thumb_deleted = True
                                    logger.info(f"✅ Deleted thumbnail from GCS: {thumb_path}")
                                except Exception as e:
                                    logger.error(f"❌ Failed to delete thumbnail {thumb_path}: {e}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not derive/delete thumbnail path from {file_path}: {e}")
            
            return {
                'main_deleted': main_deleted,
                'thumb_deleted': thumb_deleted,
                'message': f"Deleted file{' and thumbnail' if thumb_deleted else ''}"
            }
            
        except Exception as e:
            logger.error(f"❌ Error deleting file from GCS: {e}")
            raise Exception(f'Failed to delete file: {str(e)}')

