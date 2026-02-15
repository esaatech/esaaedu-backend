# Student Project Submission Workflow

## Overview

This document describes how student project submission works, including the scheduling requirement and how submission types are determined from ClassEvent when projects are scheduled.

## Key Concepts

### Project Scheduling
- Projects must be **scheduled** (have an associated ClassEvent) before students can submit
- When a project is scheduled, the teacher sets:
  - `project_platform` (e.g., Ace Pyodide, Trinket)
  - `submission_type` (e.g., 'code', 'note', 'link', etc.)
- These values are stored in the ClassEvent, not the Project model
- The Project model's `submission_type` is optional and used as a fallback

### Submission Requirements
- **Unscheduled projects**: Submission is disabled, students see a message
- **Scheduled projects**: Submission is enabled based on the submission_type from ClassEvent
- **Already submitted projects**: Students can view their submissions even if project becomes unscheduled
- **Graded projects**: Always viewable via ProjectDetailPage

## API Endpoints

### Get Student Course Projects

**Endpoint**: `GET /api/courses/student/courses/{course_id}/projects/`

**Authentication**: Required (IsAuthenticated)

**Permissions**: 
- User must be enrolled in the course
- Enrollment status must be 'active' or 'completed'

**Request**:
- `course_id` in URL path (UUID)

**Response** (200 OK):
```json
{
    "course_id": "course-uuid",
    "course_title": "Course Name",
    "projects": [
        {
            "id": "project-uuid",
            "title": "Project Title",
            "instructions": "Project instructions...",
            "submission_type": "code",  // From ClassEvent if scheduled, else from Project
            "project_platform": {      // From ClassEvent if scheduled, else null
                "id": "platform-uuid",
                "name": "ace_pyodide",
                "display_name": "Ace Pyodide",
                "base_url": "https://..."
            },
            "is_scheduled": true,       // Whether project has ClassEvent
            "points": 100,
            "due_at": "2024-01-31T23:00:00Z",
            "order": 1,
            "created_at": "2024-01-01T10:00:00Z"
        }
    ]
}
```

**Response Fields**:
- `is_scheduled` (boolean): Whether project has an associated ClassEvent
- `submission_type` (string|null): Submission type from ClassEvent (if scheduled) or Project (if not scheduled)
- `project_platform` (object|null): Platform details from ClassEvent (if scheduled) or null

**Error Responses**:
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not enrolled in course
- `404 Not Found`: Course not found
- `500 Internal Server Error`: Server error

**Implementation**: `courses/views.py::student_course_projects()`

## Serializers

### ProjectListSerializer

**Location**: `courses/serializers.py`

**Purpose**: Serialize project data for student course projects list

**Fields**:
- `id`: Project ID
- `title`: Project title
- `instructions`: Project instructions
- `submission_type`: Submission type (from ClassEvent if scheduled, else from Project)
- `project_platform`: Platform details (from ClassEvent if scheduled, else null)
- `is_scheduled`: Whether project has ClassEvent (boolean)
- `points`: Maximum points
- `due_at`: Due date
- `order`: Project order in course
- `created_at`: Creation timestamp

**Methods**:

#### `get_is_scheduled(self, obj)`
Checks if any ClassEvent exists for this project.

**Returns**: `True` if ClassEvent exists, `False` otherwise

#### `get_submission_type(self, obj)`
Gets submission type from ClassEvent if available, otherwise from Project.

**Logic**:
1. Check most recent ClassEvent with `submission_type`
2. If found, return ClassEvent's `submission_type.name`
3. Otherwise, return Project's `submission_type.name` (if exists)
4. Return `None` if neither exists

**Returns**: String (submission type name) or `None`

#### `get_project_platform(self, obj)`
Gets project platform from ClassEvent if available.

**Logic**:
1. Check most recent ClassEvent with `project_platform`
2. If found, return platform details as object
3. Return `None` if no ClassEvent with platform exists

**Returns**: Object with `id`, `name`, `display_name`, `base_url` or `None`

## Frontend Behavior

### StudentProjectDetail Component

**Location**: `src/components/dashboard/StudentProjectDetail.tsx`

**Submission Logic**:
```typescript
const isScheduled = project.is_scheduled ?? false;
const isSubmitted = submission && (submission.status === 'SUBMITTED' || submission.status === 'GRADED');
const canSubmit = isScheduled || isSubmitted;
```

**Behavior**:

1. **Unscheduled Projects** (`is_scheduled === false`):
   - Shows warning message: "This project has not been scheduled yet"
   - Disables all submission inputs
   - Disables "Submit" tab
   - Disables submit button
   - **Exception**: If student has already submitted, they can view their submission

2. **Scheduled Projects** (`is_scheduled === true`):
   - Enables submission based on `submission_type`:
     - `'code'` + `project_platform.name === 'ace_pyodide'`: Shows Ace Pyodide IDE
     - `'code'`: Shows code editor
     - `'note'`: Shows text area
     - `'link'`: Shows URL input
     - Other types: Shows appropriate file upload

3. **Already Submitted Projects**:
   - Can view submission (read-only)
   - Cannot re-submit (unless teacher returns it)
   - Works even if project becomes unscheduled later

4. **Graded Projects**:
   - Shows ProjectDetailPage with grades and feedback
   - Always accessible regardless of scheduling status

## Workflow

### Teacher Workflow

1. **Create Project**: Teacher creates a project in the course
   - Project may have optional `submission_type` and `project_platform` at creation
   - These are defaults, not enforced

2. **Schedule Project**: Teacher schedules project as ClassEvent
   - Sets `project_platform` (e.g., Ace Pyodide)
   - Sets `submission_type` (e.g., 'code')
   - Sets `due_date`
   - **Note**: For Ace Pyodide, `submission_type` is automatically set to 'code'

3. **Student Access**: Student can now see project with:
   - `is_scheduled: true`
   - `submission_type` from ClassEvent
   - `project_platform` from ClassEvent
   - Submission form enabled

### Student Workflow

1. **View Project**: Student opens project from course
   - If not scheduled: Sees warning, submission disabled
   - If scheduled: Sees appropriate submission form based on type

2. **Submit Project**: Student completes and submits
   - Submission is saved with status 'SUBMITTED'
   - Can view submission even if project becomes unscheduled later

3. **View Graded Project**: After teacher grades
   - Shows ProjectDetailPage with grades and feedback
   - Always accessible

## Edge Cases Handled

### 1. Project Becomes Unscheduled After Submission
- **Scenario**: Student submits when scheduled, teacher later unschedules
- **Behavior**: Student can still view their submission
- **Reason**: `canSubmit = isScheduled || isSubmitted` allows viewing existing submissions

### 2. Project Re-scheduled with Different Type
- **Scenario**: Project scheduled as 'note', student submits, then re-scheduled as 'code'
- **Behavior**: 
  - Existing submission is preserved and viewable
  - New submission type is available for new submissions
  - Student sees both old submission and new requirements

### 3. Project Never Scheduled
- **Scenario**: Project created but never scheduled
- **Behavior**: 
  - `is_scheduled: false`
  - Submission form disabled
  - Warning message shown
  - Students cannot submit

### 4. Project Scheduled Without Platform/Type
- **Scenario**: ClassEvent created but `project_platform` or `submission_type` not set
- **Behavior**: 
  - `is_scheduled: true` (enables submission)
  - `submission_type` falls back to Project's value (if exists)
  - `project_platform` is `null` (if not in ClassEvent)

## Security Considerations

1. **Enrollment Check**: Students can only see projects for courses they're enrolled in
2. **Submission Ownership**: Students can only submit/view their own submissions
3. **Scheduling Requirement**: Prevents premature submissions before teacher configures project
4. **Data Preservation**: Existing submissions remain accessible even if project configuration changes

## Related Files

- `courses/models.py` - Project, ClassEvent, ProjectSubmission models
- `courses/serializers.py` - ProjectListSerializer, StudentProjectSubmissionSerializer
- `courses/views.py` - student_course_projects, student_project_submit, student_project_submission_detail
- `courses/urls.py` - URL routing
- `src/components/dashboard/StudentProjectDetail.tsx` - Frontend submission component
- `src/services/api.ts` - getStudentCourseProjects API method

## Migration Notes

No database migrations required. This feature uses existing ClassEvent model fields:
- `project_platform` (ForeignKey to ProjectPlatform)
- `submission_type` (ForeignKey to SubmissionType)

## Future Enhancements

1. **Submission Type Validation**: Validate submission_type matches project_platform requirements
2. **Scheduling Notifications**: Notify students when projects are scheduled
3. **Submission Deadlines**: Enforce due_date from ClassEvent
4. **Multiple Submissions**: Allow re-submission if teacher returns project
5. **Draft Saving**: Enhanced draft saving for unscheduled projects (currently disabled)




