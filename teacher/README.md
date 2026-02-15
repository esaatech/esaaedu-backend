# Teacher App

## Overview
This app handles teacher-specific functionality for the Little Learners Tech platform.

## Note
⚠️ **This app was created later in the development process.** Most teacher-related views and functionality are still located in the `courses` app. This app will gradually be expanded to consolidate all teacher-specific features.

## Current Structure
- **Models**: Teacher profile management
- **Views**: Teacher profile CRUD operations, file upload/delete endpoints
- **Serializers**: Teacher profile data serialization
- **URLs**: Teacher profile endpoints, file management endpoints
- **Utils**: Shared file upload utility service

## File Upload Service

### Location
`teacher/utils.py`

### Purpose
The `FileUploadService` class provides a centralized utility for handling file uploads and deletions to Google Cloud Storage. It's used by both teacher and student views to ensure consistent behavior across the platform.

### Key Features

1. **File Type Detection**: Automatically detects file type (image, video, audio, document, other) from MIME type and extension
2. **Image Processing**: For images, automatically:
   - Compresses to max 1920x1920 (maintains aspect ratio)
   - Generates 400x400 thumbnails
   - Converts to JPEG format with 85% quality
   - Handles transparency (converts RGBA/LA/P to RGB with white background)
3. **File Size Validation**: Enforces size limits based on file type:
   - Images: 10MB
   - Videos: 500MB
   - Audio: 100MB
   - Documents: 50MB
   - Other: 50MB
4. **Thumbnail Management**: Automatically handles thumbnail creation and deletion for images
5. **GCS Integration**: Handles uploads to Google Cloud Storage with proper URL generation

### Usage

#### Upload File

```python
from teacher.utils import FileUploadService

# In a view
uploaded_file = request.FILES.get('file')
storage_path = request.data.get('path', 'assignment_files')

try:
    result = FileUploadService.upload_file(uploaded_file, storage_path)
    # result contains:
    # - file_url: GCS URL
    # - file_size: Size in bytes
    # - file_size_mb: Size in MB
    # - file_extension: File extension
    # - mime_type: MIME type
    # - file_type: Detected type
    # - original_filename: Original filename
    # - thumbnail_url: Thumbnail URL (only for images)
except ValueError as e:
    # File validation error
    pass
except Exception as e:
    # Upload/processing error
    pass
```

#### Delete File

```python
from teacher.utils import FileUploadService

file_url = "https://storage.googleapis.com/bucket/path/to/file.jpg"

try:
    result = FileUploadService.delete_file(file_url)
    # result contains:
    # - main_deleted: Boolean indicating if main file was deleted
    # - thumb_deleted: Boolean indicating if thumbnail was deleted
    # - message: Success message
except Exception as e:
    # Deletion error
    pass
```

### Methods

#### `detect_file_type(mime_type: str, file_extension: str) -> str`
Detects file type from MIME type and extension. Returns: `'image'`, `'video'`, `'audio'`, `'document'`, or `'other'`.

#### `get_max_size(file_type: str) -> int`
Returns maximum allowed file size in bytes for the given file type.

#### `handle_image_upload(uploaded_file, storage_path: str, original_filename: str, file_extension: str, mime_type: str) -> dict`
Handles image upload with compression and thumbnail generation. Returns file metadata dictionary.

#### `handle_other_file_upload(uploaded_file, storage_path: str, original_filename: str, file_extension: str, mime_type: str, file_type: str) -> dict`
Handles non-image file upload. Returns file metadata dictionary.

#### `upload_file(uploaded_file, storage_path: str = 'files') -> dict`
Main entry point for file upload. Handles validation, file type detection, and uploads to GCS. Returns file metadata dictionary.

#### `delete_file(file_url: str) -> dict`
Deletes a file from GCS by URL. For images, also deletes the associated thumbnail. Returns deletion status dictionary.

### Used By

- **Teacher Views**: `AllFileUploadView`, `AllFileDeleteView` in `teacher/views.py`
- **Student Views**: `StudentFileUploadView`, `StudentFileDeleteView` in `student/views.py`

### Storage Path Structure

Files are organized in GCS as follows:
```
{storage_path}/
  images/
    {uuid}-{filename}.jpg
    thumbnails/
      {uuid}-{filename}-thumb.jpg
  videos/
    {uuid}-{filename}.mp4
  audio/
    {uuid}-{filename}.mp3
  documents/
    {uuid}-{filename}.pdf
  other/
    {uuid}-{filename}.ext
```

## API Endpoints

### File Upload (Teacher)
- **URL**: `/api/teacher/files/upload/`
- **Method**: POST
- **View**: `AllFileUploadView`
- **Permission**: `IsAuthenticated` + Teacher role check
- **Request**: Multipart form data with `file` and optional `path`
- **Response**: File metadata including `file_url`, `file_size`, `thumbnail_url` (for images), etc.

### File Delete (Teacher)
- **URL**: `/api/teacher/files/delete/`
- **Method**: DELETE
- **View**: `AllFileDeleteView`
- **Permission**: `IsAuthenticated` + Teacher role check
- **Request**: JSON with `file_url`
- **Response**: Deletion status with `main_deleted` and `thumb_deleted` booleans

## Future Migration
The following functionality will be moved from the `courses` app to this app:
- Teacher dashboard views
- Course management views
- Student management views
- Class scheduling views
- Quiz and lesson management views

## Dependencies
- `users` app (for User and TeacherProfile models)
- `courses` app (for course-related functionality)
- `django-storages` (for Google Cloud Storage integration)
- `Pillow` (for image processing)