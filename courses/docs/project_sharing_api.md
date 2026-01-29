# Project Sharing API - Backend Implementation

## Overview

This document describes the backend implementation for the project sharing feature, which allows students to generate shareable links for their graded projects that can be accessed publicly without authentication.

## Database Changes

### Model: ProjectSubmission

**Location**: `courses/models.py`

**New Field**:
```python
share_token = models.CharField(
    max_length=64,
    unique=True,
    null=True,
    blank=True,
    help_text="Unique token for sharing project submission publicly"
)
```

**New Methods**:
```python
def generate_share_token(self):
    """Generate a unique share token for this submission"""
    if not self.share_token:
        self.share_token = secrets.token_urlsafe(32)
        self.save(update_fields=['share_token'])
    return self.share_token

@property
def share_url(self):
    """Get the shareable URL for this project submission"""
    if self.share_token:
        return f"/project/{self.share_token}"
    return None
```

**Migration**: `0052_add_share_token_to_project_submission.py`

## API Endpoints

### 1. Generate Share Token

**Endpoint**: `POST /api/courses/student/projects/submissions/{submission_id}/share/`

**Authentication**: Required (IsAuthenticated)

**Permissions**: 
- User must own the submission
- Submission must be graded (status='GRADED')

**Request**:
- No body required
- `submission_id` in URL path (UUID)

**Response** (200 OK):
```json
{
    "share_token": "abc123xyz...",
    "share_url": "https://domain.com/project/abc123xyz..."
}
```

**Error Responses**:
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: User does not own the submission
- `400 Bad Request`: Submission is not graded
- `404 Not Found`: Submission does not exist
- `500 Internal Server Error`: Server error

**Implementation**: `courses/views.py::generate_project_share_token()`

### 2. Get Shared Project (Public)

**Endpoint**: `GET /api/courses/student/projects/submissions/share/{share_token}/`

**Authentication**: None (Public access)

**Request**:
- `share_token` in URL path (string)

**Response** (200 OK):
```json
{
    "id": "submission-uuid",
    "project": {
        "id": "project-uuid",
        "title": "Project Title",
        "instructions": "Project instructions...",
        "submission_type": "code",
        "project_platform": {
            "id": "platform-uuid",
            "name": "ace_pyodide",
            "display_name": "Ace Pyodide",
            "base_url": "https://..."
        }
    },
    "student": {
        "id": "student-uuid",
        "name": "Student Name",
        "first_name": "First",
        "last_name": "Last",
        "email": "student@example.com"
    },
    "course_title": "Course Name",
    "content": "Code or text content...",
    "file_url": "https://...",
    "submitted_at": "2024-01-01T12:00:00Z",
    "created_at": "2024-01-01T10:00:00Z"
}
```

**Note**: Response excludes sensitive information:
- `points_earned`
- `points_possible`
- `percentage`
- `feedback`
- `feedback_response`
- `grader` information

**Error Responses**:
- `404 Not Found`: Invalid share token or submission not available for sharing
- `500 Internal Server Error`: Server error

**Implementation**: `courses/views.py::get_shared_project_submission()`

## Serializers

### PublicProjectSubmissionSerializer

**Location**: `courses/serializers.py`

**Purpose**: Serialize project submission data for public access (excludes sensitive information)

**Fields**:
- `id`: Submission ID
- `project`: Project details (nested object)
- `student`: Student information (nested object)
- `course_title`: Course name
- `content`: Submission content
- `file_url`: File URL if applicable
- `submitted_at`: Submission timestamp
- `created_at`: Creation timestamp

**Excluded Fields**:
- `points_earned`
- `points_possible`
- `percentage`
- `feedback`
- `feedback_response`
- `grader`
- `status` (only graded submissions can be shared)

### StudentProjectSubmissionSerializer

**Location**: `courses/serializers.py`

**Update**: Added `share_token` field to allow students to see their share tokens

**Fields**:
- `id`: Submission ID
- `project`: Project ID
- `project_title`: Project title (from project)
- `project_points`: Project points (from project)
- `project_instructions`: Project instructions (from project)
- `submission_type`: Submission type (from ClassEvent if available, else Project)
- `project_platform`: Platform details (from ClassEvent if available, else null)
- `status`: Submission status
- `content`: Submission content
- `file_url`: File URL if applicable
- `reflection`: Student reflection
- `submitted_at`: Submission timestamp
- `graded_at`: Grading timestamp
- `points_earned`: Points awarded
- `points_possible`: Total points possible
- `percentage`: Score percentage
- `passed`: Whether student passed
- `is_graded`: Whether submission is graded
- `feedback`: Teacher feedback
- `feedback_response`: Student response to feedback
- `feedback_checked`: Whether student has seen feedback
- `feedback_checked_at`: When feedback was checked
- `grader_name`: Name of grader
- `share_token`: Share token for public sharing
- `created_at`: Creation timestamp
- `updated_at`: Update timestamp

**Methods**:
- `get_submission_type()`: Gets submission_type from ClassEvent (if available) or Project
- `get_project_platform()`: Gets project_platform from ClassEvent (if available)

## Dashboard Overview Updates

### Project Assessments List

**Location**: `student/views.py::DashboardOverview`

**New Response Field**: `project_assessments` (array)

**Structure**:
```python
project_assessments = [
    {
        'project_id': str(submission.project.id),
        'submission_id': str(submission.id),
        'project_title': submission.project.title,
        'course_title': submission.project.course.title,
        'course_id': str(submission.project.course.id),
        'student_name': f"{first_name} {last_name}",
        'score_percentage': float(percentage) or None,
        'passed': bool or None,
        'is_graded': bool,
        'status': str,
        'submitted_at': str (ISO format) or None,
        'graded_at': str (ISO format) or None,
        'has_teacher_feedback': bool,
    },
    ...
]
```

**Ordering**: Sorted by `submitted_at` descending (most recent first)

**Filtering**: Only includes submissions with status `'SUBMITTED'` or `'GRADED'`

## Security Considerations

1. **Token Generation**:
   - Uses `secrets.token_urlsafe(32)` for cryptographically secure tokens
   - Tokens are 32 bytes, URL-safe encoded (approximately 43 characters)
   - Unique constraint at database level

2. **Access Control**:
   - Only submission owners can generate share tokens
   - Only graded submissions can be shared
   - Public endpoint validates token before returning data

3. **Data Sanitization**:
   - Public serializer excludes all sensitive information
   - No grades, feedback, or internal IDs exposed
   - Student email included (may want to make optional in future)

4. **Token Validation**:
   - Token must exist in database
   - Submission must be graded
   - No expiration (tokens persist for lifetime of submission)

## URL Configuration

**Location**: `courses/urls.py`

```python
path('student/projects/submissions/<uuid:submission_id>/share/', 
     views.generate_project_share_token, 
     name='generate_project_share_token'),
path('student/projects/submissions/share/<str:share_token>/', 
     views.get_shared_project_submission, 
     name='get_shared_project_submission'),
```

## Error Handling

### generate_project_share_token

- Validates user authentication
- Checks submission ownership
- Validates submission status (must be GRADED)
- Handles database errors gracefully
- Returns appropriate HTTP status codes

### get_shared_project_submission

- Validates share token exists
- Checks submission is graded
- Handles missing submissions
- Returns 404 for invalid tokens (security: doesn't reveal if token is invalid vs submission not shareable)

## Testing

### Unit Tests Recommended

1. **Model Tests**:
   - `generate_share_token()` generates unique tokens
   - `share_url` property returns correct format
   - Token persists after generation

2. **API Tests**:
   - Generate token requires authentication
   - Generate token requires ownership
   - Generate token requires graded status
   - Public endpoint returns correct data
   - Public endpoint excludes sensitive fields
   - Invalid tokens return 404

3. **Serializer Tests**:
   - PublicProjectSubmissionSerializer excludes sensitive fields
   - StudentProjectSubmissionSerializer includes share_token

## Related Files

- `courses/models.py` - ProjectSubmission model
- `courses/views.py` - API endpoints
- `courses/serializers.py` - Serializers
- `courses/urls.py` - URL routing
- `student/views.py` - Dashboard overview
- `courses/migrations/0052_add_share_token_to_project_submission.py` - Migration

## Related Documentation

- `student_project_submission_workflow.md` - Complete workflow for student project submission, including scheduling requirements, ClassEvent integration, and submission type handling

## Migration Instructions

```bash
cd /path/to/django/esaaedu-backend
poetry run python manage.py migrate
```

## Future Enhancements

1. **Token Expiration**: Optional expiration dates for share links
2. **Password Protection**: Optional password protection for share links
3. **Access Logging**: Track views and engagement on shared projects
4. **Revocation**: Allow students to revoke share tokens
5. **Analytics**: Track number of views per shared project
6. **Custom URLs**: Allow students to set custom share URLs

