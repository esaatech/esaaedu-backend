# Student App

## Overview
This app handles student-specific functionality for the Little Learners Tech platform, including course enrollment, lesson progress, assignment submissions, and file management.

## File Upload/Delete Endpoints

### Student File Upload

**Location**: `student/views.py` - `StudentFileUploadView`

**URL**: `/api/student/files/upload/`

**Method**: POST

**Permission**: `IsAuthenticated` + Student role check

**Purpose**: Allows students to upload files (images, videos, documents, etc.) for use in assignment submissions, particularly essay answers.

**Request**:
- Content-Type: `multipart/form-data`
- `file`: File to upload (required)
- `path`: Optional storage path (defaults to `'assignment_files'`)

**Response**:
```json
{
  "file_url": "https://storage.googleapis.com/bucket/assignment_files/images/uuid-filename.jpg",
  "file_size": 1024000,
  "file_size_mb": 1.0,
  "file_extension": "jpg",
  "mime_type": "image/jpeg",
  "file_type": "image",
  "original_filename": "image.jpg",
  "thumbnail_url": "https://storage.googleapis.com/bucket/assignment_files/images/thumbnails/uuid-filename-thumb.jpg"
}
```

**Implementation Details**:
- Uses the shared `FileUploadService` utility from `teacher.utils` for consistent behavior
- Validates file type and size based on file type (images: 10MB, videos: 500MB, etc.)
- For images: Automatically compresses and generates thumbnails
- Returns full file metadata including GCS URLs

**Error Responses**:
- `403 Forbidden`: User is not a student
- `400 Bad Request`: No file provided or file validation failed
- `500 Internal Server Error`: Upload or processing failed

### Student File Delete

**Location**: `student/views.py` - `StudentFileDeleteView`

**URL**: `/api/student/files/delete/`

**Method**: DELETE

**Permission**: `IsAuthenticated` + Student role check

**Purpose**: Allows students to delete files from GCS, particularly when removing images/files from essay answers.

**Request**:
- Content-Type: `application/json`
- Body:
```json
{
  "file_url": "https://storage.googleapis.com/bucket/path/to/file.jpg"
}
```

**Response**:
```json
{
  "message": "File deleted successfully (and thumbnail)"
}
```

**Implementation Details**:
- Uses the shared `FileUploadService.delete_file()` utility
- For images: Automatically deletes both the main file and its thumbnail
- Handles URL parsing and path extraction from GCS URLs
- Returns success message indicating what was deleted

**Error Responses**:
- `403 Forbidden`: User is not a student
- `400 Bad Request`: `file_url` not provided
- `500 Internal Server Error`: Deletion failed

## Usage in Assignment Submissions

These endpoints are primarily used when students complete essay questions in assignments and assessments:

1. **Upload**: When a student adds an image, video, or file to their essay answer using the BlockNote editor
2. **Delete**: When a student removes an image/file from their essay answer before saving

The frontend uses these endpoints via:
- `apiService.uploadStudentFile()` - Calls `/api/student/files/upload/`
- `apiService.deleteStudentFile()` - Calls `/api/student/files/delete/`

## Shared Utility

Both endpoints use the `FileUploadService` utility class from `teacher.utils` to ensure:
- Consistent file handling logic
- Same validation rules
- Same storage structure
- Same image processing (compression, thumbnails)

This promotes code reusability and maintainability. See `teacher/README.md` for detailed documentation on `FileUploadService`.

## Dependencies

- `teacher.utils.FileUploadService` - Shared file upload utility
- `django-storages` - Google Cloud Storage integration
- `Pillow` - Image processing (for image uploads)

## Related Documentation

- `teacher/README.md` - FileUploadService utility documentation
- Frontend: `docs/blocknote-implementation.md` - Student essay answer implementation
- Frontend: `src/docs/components/assignment-components.md` - Assignment component documentation

