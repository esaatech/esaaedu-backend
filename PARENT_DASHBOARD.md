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


