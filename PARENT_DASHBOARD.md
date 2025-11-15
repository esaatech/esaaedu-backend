# Parent Dashboard - Student Performance Aggregates

## Overview

This document describes the implementation of high-level student performance aggregates in the `StudentProfile` model to support the parent dashboard. These aggregates provide a quick overview of a student's performance across all enrolled courses without requiring complex database queries.

## Problem Statement

The parent dashboard needs to display:
- Overall quiz average score across all courses
- Overall assignment average score across all courses
- Combined overall average score
- Total quizzes and assignments completed

Previously, this required querying all enrollments, quiz attempts, and assignment submissions for each student, which was slow and inefficient.

## Solution

We implemented **denormalized aggregate fields** in the `StudentProfile` model that are automatically maintained via Django signals. This provides:
- **Fast queries**: No joins needed for dashboard display
- **Automatic updates**: Aggregates update when quizzes/assignments are completed
- **Accurate calculations**: Weighted averages based on actual completion counts

## Fields Added to StudentProfile Model

### Location
`users/models.py` - `StudentProfile` class

### New Fields

```python
# Performance Aggregates (denormalized for fast dashboard queries)
total_quizzes_completed = models.PositiveIntegerField(
    default=0,
    help_text="Total number of completed quiz attempts across all courses"
)

total_assignments_completed = models.PositiveIntegerField(
    default=0,
    help_text="Total number of completed assignment submissions across all courses"
)

overall_quiz_average_score = models.DecimalField(
    max_digits=5,
    decimal_places=2,
    null=True,
    blank=True,
    help_text="Overall average quiz score percentage across all courses"
)

overall_assignment_average_score = models.DecimalField(
    max_digits=5,
    decimal_places=2,
    null=True,
    blank=True,
    help_text="Overall average assignment score percentage across all courses"
)

overall_average_score = models.DecimalField(
    max_digits=5,
    decimal_places=2,
    null=True,
    blank=True,
    help_text="Combined average of quiz and assignment scores"
)

last_performance_update = models.DateTimeField(
    null=True,
    blank=True,
    help_text="Timestamp of last performance aggregate update"
)
```

## How It Works

### Calculation Method

#### Quiz Aggregates
Uses **weighted average** based on number of quizzes completed per course:

```
Overall Quiz Average = (Course1_avg × Course1_count + Course2_avg × Course2_count + ...) / Total_quizzes
```

**Example:**
- Course A: 80% average (3 quizzes)
- Course B: 90% average (2 quizzes)
- Course C: 85% average (5 quizzes)

**Calculation:**
```
Total = (80 × 3) + (90 × 2) + (85 × 5) = 240 + 180 + 425 = 845
Overall = 845 / 10 = 84.5%
```

#### Assignment Aggregates
Uses **weighted average** based on number of assignments completed per course:

```
Overall Assignment Average = (Course1_avg × Course1_count + Course2_avg × Course2_count + ...) / Total_assignments
```

**Example:**
- Course A: 75% average (5 assignments)
- Course B: 88% average (3 assignments)

**Calculation:**
```
Total = (75 × 5) + (88 × 3) = 375 + 264 = 639
Overall = 639 / 8 = 79.875% ≈ 79.88%
```

#### Combined Overall Average
Weighted average of quiz and assignment scores:

```
Overall Average = (Quiz_avg × Quiz_count + Assignment_avg × Assignment_count) / (Quiz_count + Assignment_count)
```

### Implementation Details

#### 1. Recalculation Methods

Three methods were added to `StudentProfile`:

**`recalculate_quiz_aggregates()`**
- Iterates through all active/completed enrollments
- Uses `enrollment.total_quizzes_taken` as weight
- Calculates weighted average of `enrollment.average_quiz_score`
- Updates `total_quizzes_completed` and `overall_quiz_average_score`

**`recalculate_assignment_aggregates()`**
- Iterates through all active/completed enrollments
- Uses `enrollment.total_assignments_completed` as weight
- Calculates weighted average of `enrollment.average_assignment_score`
- Updates `total_assignments_completed` and `overall_assignment_average_score`

**`recalculate_overall_average()`**
- Combines quiz and assignment averages using weighted average
- Updates `overall_average_score`

#### 2. Automatic Updates via Signals

**Location:** `users/signals.py`

**Signal Handlers:**

```python
@receiver(post_save, sender=QuizAttempt)
def update_student_quiz_aggregates(sender, instance, **kwargs):
    """Triggers when a quiz attempt is completed/graded"""
    if instance.completed_at and instance.score is not None:
        instance.student.student_profile.recalculate_quiz_aggregates()

@receiver(post_save, sender=AssignmentSubmission)
def update_student_assignment_aggregates(sender, instance, **kwargs):
    """Triggers when an assignment is graded"""
    if instance.is_graded and instance.percentage is not None:
        instance.student.student_profile.recalculate_assignment_aggregates()
```

**Signal Registration:** `users/apps.py`
```python
def ready(self):
    import users.signals  # noqa
```

### 3. One-Time Backfill

For existing data, a management command was created to backfill aggregates for all students.

**Location:** `users/management/commands/backfill_student_aggregates.py`

**Usage:**
```bash
# Backfill all students
python manage.py backfill_student_aggregates

# Dry run (preview changes)
python manage.py backfill_student_aggregates --dry-run

# Update specific student
python manage.py backfill_student_aggregates --student-id <user_id>
```

**What it does:**
- Iterates through all `StudentProfile` records
- Calls `recalculate_quiz_aggregates()` and `recalculate_assignment_aggregates()` for each
- Provides progress output and error handling
- Uses database transactions for safety

## Database Migration

A migration was created to add the new fields:

**File:** `users/migrations/0004_studentprofile_last_performance_update_and_more.py`

**Fields added:**
- `total_quizzes_completed`
- `total_assignments_completed`
- `overall_quiz_average_score`
- `overall_assignment_average_score`
- `overall_average_score`
- `last_performance_update`

## Admin Interface Updates

**Location:** `users/admin.py`

The Django admin was updated to display the new fields:

**List Display:**
- Added `overall_quiz_average_score`
- Added `overall_assignment_average_score`
- Added `overall_average_score`

**Readonly Fields:**
All performance aggregates are marked as readonly since they're auto-calculated.

**New Fieldset:**
Added "Performance Aggregates" section showing all aggregate fields with description.

## Usage in Views/API

### Accessing Aggregates

```python
from users.models import StudentProfile

# Get student profile
student_profile = request.user.student_profile

# Access aggregates directly
quiz_avg = student_profile.overall_quiz_average_score
assignment_avg = student_profile.overall_assignment_average_score
overall_avg = student_profile.overall_average_score
total_quizzes = student_profile.total_quizzes_completed
total_assignments = student_profile.total_assignments_completed
```

### Example API Response

```json
{
  "student_profile": {
    "overall_quiz_average_score": 84.50,
    "overall_assignment_average_score": 79.88,
    "overall_average_score": 82.19,
    "total_quizzes_completed": 10,
    "total_assignments_completed": 8,
    "last_performance_update": "2024-01-15T10:30:00Z"
  }
}
```

## Data Flow

```
┌─────────────────────┐
│  Student completes  │
│  quiz/assignment    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  QuizAttempt/       │
│  AssignmentSubmission│
│  saved              │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Signal triggered   │
│  (post_save)        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  EnrolledCourse     │
│  average updated    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  StudentProfile     │
│  recalculate_*()   │
│  called             │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Aggregates updated │
│  in StudentProfile  │
└─────────────────────┘
```

## Performance Considerations

### Benefits
- **Fast dashboard queries**: Single query to `StudentProfile` instead of multiple joins
- **Reduced database load**: Aggregates calculated once, not on every request
- **Scalable**: Performance doesn't degrade as student enrollments grow

### Trade-offs
- **Denormalization**: Data stored in multiple places (course-level and student-level)
- **Consistency**: Relies on signals to keep aggregates in sync
- **Storage**: Additional fields in `StudentProfile` table

### Mitigation
- Signals ensure automatic updates
- Recalculation methods can be called manually if needed
- Backfill command available for data fixes

## Maintenance

### Manual Recalculation

If aggregates become out of sync, they can be manually recalculated:

```python
from users.models import StudentProfile

student_profile = StudentProfile.objects.get(user=some_user)
student_profile.recalculate_quiz_aggregates()
student_profile.recalculate_assignment_aggregates()
```

### Monitoring

Check `last_performance_update` timestamp to verify aggregates are being updated:
- Should update whenever a quiz/assignment is completed
- If timestamp is stale, investigate signal handlers

### Troubleshooting

**Aggregates not updating:**
1. Check if signals are registered in `users/apps.py`
2. Verify signal handlers in `users/signals.py`
3. Check Django logs for signal errors

**Incorrect values:**
1. Run backfill command to recalculate all aggregates
2. Verify course-level averages are correct first
3. Check for edge cases (zero quizzes/assignments, etc.)

## Future Enhancements

Potential improvements:
- Add historical tracking (aggregates over time)
- Add course-specific breakdowns
- Add trend analysis (improving/declining)
- Add caching layer for even faster queries
- Add admin action to recalculate selected students

## Related Files

- `users/models.py` - Model definition and recalculation methods
- `users/signals.py` - Signal handlers for automatic updates
- `users/apps.py` - Signal registration
- `users/admin.py` - Admin interface configuration
- `users/management/commands/backfill_student_aggregates.py` - One-time backfill command
- `users/migrations/0004_*.py` - Database migration

## Summary

This implementation provides efficient, automatically-maintained performance aggregates for the parent dashboard. The weighted average approach ensures accurate representation of student performance across all courses, while the signal-based updates maintain data consistency automatically.

---

# Parent Dashboard API - Complete Implementation

## Overview

The Parent Dashboard API provides comprehensive data for parents to monitor their child's academic performance, upcoming tasks, and receive messages from teachers and administrators.

## API Endpoint

**Base URL:** `/api/student/parent/dashboard/`

**Method:** `GET`

**Authentication:** Required (Bearer token)

**View Class:** `ParentDashboardView` (located in `student/views.py`)

## Response Structure

```json
{
  "children": [...],
  "recent_activities": [...],
  "upcoming_tasks": [...],
  "performance_data": [...],
  "single_course_data": {...},
  "notifications": [...],
  "weekly_stats": {...}
}
```

## Data Sections

### 1. Weekly Performance Trends

**Method:** `get_weekly_stats()`

**Data Source:** `StudentWeeklyPerformance` model

**Returns:**
- `weekly_trend`: Array of weekly performance data (last 6 weeks)
- `total_weeks`: Number of weeks with data

**Weekly Trend Item Structure:**
```json
{
  "week": "W1",
  "year": 2024,
  "week_number": 1,
  "overall_avg": 85.5,
  "quiz_avg": 88.0,
  "assignment_avg": 83.0,
  "quiz_count": 5,
  "assignment_count": 3
}
```

**Implementation Notes:**
- Fetches last 6 weeks ordered by year and week_number (descending)
- Reverses order to show oldest to newest (W1 → W6)
- Calculates overall average from quiz and assignment averages
- Returns empty array if `StudentWeeklyPerformance` table doesn't exist

### 2. Course Performance Data

**Method:** `get_performance_data()`

**Returns:** Array of course performance summaries

**Structure:**
```json
{
  "subject": "Course Name",
  "score": 82,
  "trend": "stable"
}
```

**Calculation:**
- For each enrolled course:
  - Calculates quiz average from `QuizAttempt` records
  - Calculates assignment average from `AssignmentSubmission` records
  - Computes weighted overall average: `(quiz_avg × quiz_count + assignment_avg × assignment_count) / total_count`
- Only includes courses with at least one score

### 3. Detailed Course Breakdown

**Method:** `get_all_courses_detailed_data()`

**Endpoint:** `/api/student/parent/dashboard/courses-detailed/`

**View Class:** `AllCoursesDetailedView`

**Purpose:** Provides detailed breakdown for all courses (fetched asynchronously)

**Returns:** Array of course details

**Course Detail Structure:**
```json
{
  "course_name": "Course Title",
  "course_id": "uuid",
  "current_score": 82,
  "trend": "stable",
  "breakdown": [
    {
      "category": "Homework",
      "score": 80,
      "color": "bg-blue-500"
    },
    {
      "category": "Quizzes",
      "score": 85,
      "color": "bg-purple-500"
    },
    {
      "category": "Tests",
      "score": null,
      "color": "bg-green-500"
    },
    {
      "category": "Participation",
      "score": null,
      "color": "bg-orange-500"
    }
  ],
  "recent_grades": [
    {
      "assignment": "Quiz Title",
      "date": "Nov 13",
      "score": 95,
      "type": "quiz"
    }
  ]
}
```

**Breakdown Categories:**
- **Homework**: Assignment average (from `AssignmentSubmission`)
- **Quizzes**: Quiz average (from `QuizAttempt`)
- **Tests**: Currently null (no grade)
- **Participation**: Currently null (no grade)

**Recent Grades:**
- Combines last 3 quiz attempts and last 3 assignment submissions
- Sorted by date (most recent first)
- Limited to 5 total items
- Includes assignment name, date, score, and type

### 4. Upcoming Tasks

**Method:** `get_upcoming_tasks()`

**Returns:** Array of upcoming tasks from ClassEvents and Assignments

**Task Structure:**
```json
{
  "id": "uuid",
  "type": "class_event" | "assignment",
  "event_type": "lesson" | "meeting" | "project" | "break" | "assignment",
  "title": "Task Title",
  "course_name": "Course Name",
  "course_id": "uuid",
  "due_date": "2024-11-16T00:00:00Z",
  "start_time": "2024-11-16T00:00:00Z",  // For non-project events
  "end_time": "2024-11-16T01:00:00Z"     // For non-project events
}
```

**Data Sources:**

1. **ClassEvents** (all event types):
   - Filters events from classes where student is enrolled
   - For projects: Uses `due_date` field
   - For other events: Uses `start_time` as reference date
   - Includes both `start_time` and `end_time` for non-project events

2. **Assignments**:
   - Gets assignments from completed lessons (`StudentLessonProgress` where `status='completed'`)
   - Excludes assignments already submitted (`AssignmentSubmission` exists)
   - Only includes assignments with `due_date` set
   - Matches assignments to enrolled courses via lesson relationships

**Timezone Handling:**
- All datetime fields converted to UTC before serialization
- ISO format includes 'Z' suffix for JavaScript compatibility
- Frontend handles conversion to user's local timezone

### 5. Messages/Notifications

**Method:** `get_notifications()`

**Returns:** Empty array (to be implemented)

**Planned Structure:**
```json
{
  "id": "uuid",
  "type": "message" | "grade" | "reminder",
  "text": "Message content",
  "time": "1 hour ago",
  "unread": true
}
```

**Future Implementation:**
- Teacher assessments/reports for enrolled students
- Admin messages
- Grade updates
- Assignment feedback

## Performance Optimizations

### 1. Query Optimization

**Enrolled Courses Query:**
```python
enrolled_courses_queryset = EnrolledCourse.objects.filter(
    student_profile=student_profile,
    status='active'
).select_related('course').only(
    'id', 'completed_lessons_count', 'total_lessons_count', 
    'course_id', 'student_profile_id', 'average_quiz_score', 
    'average_assignment_score', 'course__title', 'course__id'
)
```

- Uses `select_related('course')` to avoid N+1 queries
- Uses `only()` to fetch only required fields
- Evaluates queryset to list before passing to helper methods

### 2. Asynchronous Data Loading

- **Initial Load**: Returns basic performance data quickly
- **Detailed Data**: `courses-detailed` endpoint fetched asynchronously via SWR
- Reduces initial page load time
- Detailed breakdown loads in background

### 3. Efficient Aggregations

- Uses enrollment's stored averages (`average_quiz_score`, `average_assignment_score`) when available
- Falls back to calculation only if stored values are null
- Reduces database queries for repeated requests

## Error Handling

All methods include try-except blocks:
- Returns empty arrays/objects on errors
- Logs errors for debugging
- Doesn't break dashboard if one section fails

## Related Files

- `student/views.py` - Main view implementation
- `student/urls.py` - URL routing
- `users/models.py` - StudentWeeklyPerformance model
- `courses/models.py` - ClassEvent, Assignment, QuizAttempt, AssignmentSubmission models
- `student/models.py` - StudentLessonProgress, EnrolledCourse models

## API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/student/parent/dashboard/` | GET | Main dashboard data |
| `/api/student/parent/dashboard/courses-detailed/` | GET | Detailed course breakdowns (async) |


