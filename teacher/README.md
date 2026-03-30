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

### Timetable (teacher)

- **URL**: `/api/teacher/timetable/`
- **Method**: GET
- **Purpose**: Return a lean weekly timetable template for all teacher classes with class/course labels and active class session slots.
- **Docs**: See [teacher/docs/timetable-endpoint.md](./docs/timetable-endpoint.md)

### Assessment AI grade (teacher)

- **URL**: `/api/teacher/assessments/{assessment_id}/grading/{submission_id}/ai-grade/`
- **Method**: POST
- **Purpose**: AI-grade tests/exams without persisting; returns grade suggestions for each provided question.
- **Behavior**:
  - Uses **hybrid grading** in `teacher/assessment_grading_helper.py`
  - Deterministic scoring for objective/structured types when `content` is present (`multiple_choice`, `true_false`, keyed `short_answer`, `fill_blank`, `matching`, `ordering`)
  - LLM scoring (`GeminiGrader`, template `assessment_grading`) for open-ended/code/ambiguous cases
  - Response shape matches assignment AI grade: `{ grades, total_score, total_possible }`
- **Request body**:
  - `questions`: list of `{ question_id, question_text, question_type, student_answer, points_possible, explanation?, rubric?, content? }`
  - `assignment_context` optional (course/assessment metadata)
- **Note**: Assignment AI grading path is unchanged and still uses `teacher/ai_grading_helper.py`.

### Assignment return (teacher)

- **URL**: `/api/teacher/assignments/{assignment_id}/grading/{submission_id}/return/`
- **Method**: POST
- **Purpose**: Return a submitted (not graded) assignment to the student as draft; optionally include per-question feedback. Clears grading progress; student can edit and resubmit.
- **Request body**: Optional `graded_questions`: list of `{ question_id, feedback }`. Stored as `return_feedback` on `AssignmentSubmission`.
- **Docs**: See [courses/docs/assignment_return_and_feedback.md](../courses/docs/assignment_return_and_feedback.md) for model fields, endpoint behavior, and how student lesson attaches feedback to questions.

### Course assessment return (test / exam)

- **URL**: `/api/teacher/assessments/{assessment_id}/grading/{submission_id}/return/`
- **Method**: POST
- **Purpose**: Return a submitted (not graded) test or exam to the student as `in_progress` on the **same attempt**; optional per-question feedback stored as `return_feedback` on `CourseAssessmentSubmission`. Clears grading fields and `submitted_at`; student can edit answers and submit again.
- **Request body**: Same optional shape as assignment return (`graded_questions` with `question_id` + `feedback`).

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

## Teacher pending submission counts (API contract)

Implementation lives in the `courses` app (`courses/teacher_pending_counts.py`, `TeacherDashboardAPIView.get_header_data`, `teacher_students_master`). These counters drive the **Students** sidebar badges and **Student Management** course dropdown—same semantics as “work waiting on the teacher,” aligned with assignments where applicable.

| Counter | Source | Pending rule |
|--------|--------|--------------|
| `pending_assignment_count` | `AssignmentSubmission` | `status='submitted'` and `is_graded=False` (scoped to the teacher’s courses via assignment → lessons → course). |
| `pending_test_submission_count` | `CourseAssessmentSubmission` + `CourseAssessment.assessment_type='test'` | `status` in `submitted` / `auto_submitted` and `is_graded=False`, **only on the latest attempt** per (student, assessment). Older attempts from retakes stay in the DB but are ignored so counts match the teacher list (`StudentAssessmentSubmissionsView`), which shows one row per assessment (latest submission). |
| `pending_exam_submission_count` | Same + `assessment_type='exam'` | Same as test (latest attempt only). |
| `pending_project_submission_count` | `ProjectSubmission` | `status='SUBMITTED'` only (excludes `RETURNED` while waiting on the student; excludes `GRADED`). |

`pending_submission_total` on the dashboard header is the sum of the four counts. Per-enrollment rows on `GET /api/courses/teacher/students/master/` expose the same four fields per student/course pair.

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