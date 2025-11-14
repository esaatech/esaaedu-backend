# Parent Dashboard - Weekly Performance Trends

## Overview

This document describes the implementation of weekly performance trend tracking for the parent dashboard. This feature provides a time-series view of student performance, showing how quiz and assignment averages change over time (week by week).

## Problem Statement

The parent dashboard needs to display:
- **Weekly trend visualization**: Show how overall performance (quiz + assignment averages) changes over time
- **Historical performance data**: Track performance across multiple weeks (typically last 6 weeks)
- **Fast queries**: Dashboard should load quickly without expensive time-series aggregations

Previously, calculating weekly trends would require:
- Querying all quiz attempts and assignment submissions
- Grouping by week
- Calculating averages for each week
- This was slow and inefficient for dashboard load times

## Solution

We implemented a **separate `StudentWeeklyPerformance` model** that stores pre-calculated weekly aggregates. This provides:
- **Fast queries**: Single query to get last N weeks of data
- **Automatic updates**: Weekly aggregates update when quizzes/assignments are completed/graded
- **Historical tracking**: Stores performance data over time for trend analysis
- **Scalable**: Performance doesn't degrade as data grows

## Model: StudentWeeklyPerformance

### Location
`users/models.py` - `StudentWeeklyPerformance` class

### Model Structure

```python
class StudentWeeklyPerformance(models.Model):
    student_profile = ForeignKey(StudentProfile)
    
    # Week identification (ISO week format)
    week_start_date = DateField()  # Monday of the week
    year = IntegerField()          # Year (e.g., 2024)
    week_number = IntegerField()   # ISO week number (1-53)
    
    # Weekly aggregates
    quiz_average = DecimalField(max_digits=5, decimal_places=2, null=True)
    quiz_count = PositiveIntegerField(default=0)
    
    assignment_average = DecimalField(max_digits=5, decimal_places=2, null=True)
    assignment_count = PositiveIntegerField(default=0)
    
    overall_average = DecimalField(max_digits=5, decimal_places=2, null=True)
    
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

### Key Features

- **Unique constraint**: `(student_profile, year, week_number)` - one record per student per week
- **Indexes**: Optimized for queries by `(student_profile, year, week_number)` and `(student_profile, week_start_date)`
- **ISO week format**: Uses ISO 8601 week standard (Monday = start of week)

## How It Works

### Week Calculation

Uses **ISO week format**:
- Week starts on **Monday**
- Week number ranges from 1-53 (ISO week standard)
- Year and week number uniquely identify a week

**Example:**
- Date: January 15, 2024 (Monday)
- ISO year: 2024
- ISO week: 3
- Week start: January 15, 2024

### Calculation Method

#### Quiz Weekly Average
Calculates average of all quiz scores completed within the week:

```
Week Quiz Average = Average(score) for all QuizAttempts where:
  - completed_at falls within the week (Monday-Sunday)
  - score is not null
```

**Example:**
- Week 3, 2024: 3 quizzes completed
- Scores: 85%, 90%, 88%
- Weekly quiz average: (85 + 90 + 88) / 3 = 87.67%

#### Assignment Weekly Average
Calculates average of all assignment scores graded within the week:

```
Week Assignment Average = Average(percentage) for all AssignmentSubmissions where:
  - graded_at (or submitted_at if not graded) falls within the week
  - is_graded = True
  - percentage is not null
```

**Example:**
- Week 3, 2024: 2 assignments graded
- Scores: 92%, 88%
- Weekly assignment average: (92 + 88) / 2 = 90%

#### Combined Overall Average
Weighted average of quiz and assignment scores for the week:

```
Week Overall Average = (Quiz_avg × Quiz_count + Assignment_avg × Assignment_count) / (Quiz_count + Assignment_count)
```

**Example:**
- Quiz average: 87.67% (3 quizzes)
- Assignment average: 90% (2 assignments)
- Overall: (87.67 × 3 + 90 × 2) / (3 + 2) = (263.01 + 180) / 5 = 88.60%

### Date Field Selection

**For Quizzes:**
- Uses `completed_at` - when the quiz was completed
- Only includes quizzes with `score is not null`

**For Assignments:**
- Prefers `graded_at` - when assignment was graded
- Falls back to `submitted_at` if `graded_at` is null
- Only includes assignments with `is_graded = True` and `percentage is not null`

## Implementation Details

### 1. Model Methods

#### `recalculate_week_averages()`
Recalculates all averages for a specific week from source data:

```python
weekly_perf.recalculate_week_averages()
```

**What it does:**
1. Queries all `QuizAttempt` records for the student in that week
2. Queries all `AssignmentSubmission` records for the student in that week
3. Calculates averages and counts
4. Calculates weighted overall average
5. Saves to database

#### `get_or_create_week_performance(student_profile, date)`
Static method to get or create a weekly performance record:

```python
weekly_perf, created = StudentWeeklyPerformance.get_or_create_week_performance(
    student_profile,
    datetime.now()
)
```

**What it does:**
1. Determines the ISO week for the given date
2. Gets or creates a `StudentWeeklyPerformance` record for that week
3. Returns the record and whether it was created

#### `update_weekly_performance(student_profile, completion_date)`
Static method called from signal handlers:

```python
StudentWeeklyPerformance.update_weekly_performance(
    student_profile,
    completion_date
)
```

**What it does:**
1. Gets or creates the weekly performance record for the week
2. Recalculates all averages for that week
3. Updates the record

### 2. Automatic Updates via Signals

**Location:** `users/signals.py`

**Signal Handlers:**

```python
@receiver(post_save, sender=QuizAttempt)
def update_student_quiz_aggregates(sender, instance, **kwargs):
    """Updates overall aggregates AND weekly performance"""
    if instance.completed_at and instance.score is not None:
        # Update overall aggregates
        student_profile.recalculate_quiz_aggregates()
        
        # Update weekly performance
        StudentWeeklyPerformance.update_weekly_performance(
            student_profile,
            instance.completed_at
        )

@receiver(post_save, sender=AssignmentSubmission)
def update_student_assignment_aggregates(sender, instance, **kwargs):
    """Updates overall aggregates AND weekly performance"""
    if instance.is_graded and instance.percentage is not None:
        # Update overall aggregates
        student_profile.recalculate_assignment_aggregates()
        
        # Update weekly performance
        completion_date = instance.graded_at or instance.submitted_at
        StudentWeeklyPerformance.update_weekly_performance(
            student_profile,
            completion_date
        )
```

**Signal Registration:** `users/apps.py`
```python
def ready(self):
    import users.signals  # noqa
```

### 3. Dashboard Integration

**Location:** `student/views.py` - `ParentDashboardView.get_weekly_stats()`

**Implementation:**

```python
def get_weekly_stats(self, student_profile, enrolled_courses):
    """Get last 6 weeks of performance data"""
    weekly_performance = StudentWeeklyPerformance.objects.filter(
        student_profile=student_profile
    ).order_by('-year', '-week_number')[:6]
    
    weekly_trend = []
    for wp in weekly_performance:
        weekly_trend.append({
            'week': f"W{wp.week_number}",
            'year': wp.year,
            'week_number': wp.week_number,
            'overall_avg': float(wp.overall_average) if wp.overall_average else None,
            'quiz_avg': float(wp.quiz_average) if wp.quiz_average else None,
            'assignment_avg': float(wp.assignment_average) if wp.assignment_average else None,
            'quiz_count': wp.quiz_count,
            'assignment_count': wp.assignment_count,
        })
    
    return {
        'weekly_trend': weekly_trend,
        'total_weeks': len(weekly_trend),
    }
```

**API Response Format:**

```json
{
  "weekly_stats": {
    "weekly_trend": [
      {
        "week": "W1",
        "year": 2024,
        "week_number": 1,
        "overall_avg": 85.5,
        "quiz_avg": 87.0,
        "assignment_avg": 84.0,
        "quiz_count": 3,
        "assignment_count": 2
      },
      {
        "week": "W2",
        "year": 2024,
        "week_number": 2,
        "overall_avg": 88.2,
        "quiz_avg": 90.0,
        "assignment_avg": 86.4,
        "quiz_count": 4,
        "assignment_count": 3
      }
      // ... up to 6 weeks
    ],
    "total_weeks": 6
  }
}
```

### 4. One-Time Backfill

For existing data, a management command was created to backfill weekly aggregates.

**Location:** `users/management/commands/backfill_weekly_performance.py`

**Usage:**

```bash
# Preview what will be created (dry run)
python manage.py backfill_weekly_performance --dry-run

# Backfill all students (last 12 weeks)
python manage.py backfill_weekly_performance

# Backfill specific student
python manage.py backfill_weekly_performance --student-id <user_id>

# Backfill more weeks (e.g., 24 weeks)
python manage.py backfill_weekly_performance --weeks 24
```

**What it does:**
1. Iterates through all `StudentProfile` records
2. Finds all `QuizAttempt` and `AssignmentSubmission` records in the date range
3. Groups by week
4. Creates/updates `StudentWeeklyPerformance` records for each week
5. Recalculates averages for each week

## Database Migration

A migration was created to add the new model:

**File:** `users/migrations/0005_studentweeklyperformance.py` (or next number)

**What it creates:**
- `student_weekly_performance` table
- Unique constraint on `(student_profile_id, year, week_number)`
- Indexes on `(student_profile_id, year, week_number)` and `(student_profile_id, week_start_date)`

**To apply:**

```bash
python manage.py makemigrations users
python manage.py migrate users
```

## Admin Interface

**Location:** `users/admin.py`

The Django admin was updated to display weekly performance records:

**List Display:**
- Student profile
- Year, week number, week start date
- Overall average, quiz average, assignment average
- Quiz count, assignment count
- Updated timestamp

**Filters:**
- By year
- By week number
- By updated date

**Search:**
- By student email
- By student name

**Features:**
- Read-only timestamps (`created_at`, `updated_at`)
- Ordered by year and week number (newest first)
- Grouped fieldsets for better organization

## Usage in Views/API

### Accessing Weekly Trends

```python
from users.models import StudentWeeklyPerformance

# Get last 6 weeks for a student
weekly_data = StudentWeeklyPerformance.objects.filter(
    student_profile=student_profile
).order_by('-year', '-week_number')[:6]

# Get specific week
week_data = StudentWeeklyPerformance.objects.get(
    student_profile=student_profile,
    year=2024,
    week_number=5
)

# Get all weeks in a date range
from datetime import date
start_date = date(2024, 1, 1)
end_date = date(2024, 3, 31)

weekly_data = StudentWeeklyPerformance.objects.filter(
    student_profile=student_profile,
    week_start_date__gte=start_date,
    week_start_date__lte=end_date
).order_by('week_start_date')
```

### Example API Response

```json
{
  "weekly_stats": {
    "weekly_trend": [
      {
        "week": "W1",
        "year": 2024,
        "week_number": 1,
        "overall_avg": 78.0,
        "quiz_avg": 80.0,
        "assignment_avg": 76.0,
        "quiz_count": 2,
        "assignment_count": 1
      },
      {
        "week": "W2",
        "year": 2024,
        "week_number": 2,
        "overall_avg": 82.5,
        "quiz_avg": 85.0,
        "assignment_avg": 80.0,
        "quiz_count": 3,
        "assignment_count": 2
      },
      {
        "week": "W3",
        "year": 2024,
        "week_number": 3,
        "overall_avg": 88.6,
        "quiz_avg": 87.67,
        "assignment_avg": 90.0,
        "quiz_count": 3,
        "assignment_count": 2
      }
      // ... more weeks
    ],
    "total_weeks": 6
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
           ├──────────────────────────────┐
           │                              │
           ▼                              ▼
┌─────────────────────┐      ┌─────────────────────┐
│  StudentProfile     │      │  StudentWeekly       │
│  recalculate_*()   │      │  Performance         │
│  (overall aggregates)│      │  update_weekly_*()  │
└─────────────────────┘      │  (weekly aggregates) │
                             └─────────────────────┘
```

## Performance Considerations

### Benefits

- **Fast dashboard queries**: Single query to get last N weeks instead of complex aggregations
- **Reduced database load**: Aggregates calculated once per week update, not on every request
- **Scalable**: Performance doesn't degrade as student enrollments or historical data grows
- **Indexed queries**: Database indexes optimize lookups by student and week

### Trade-offs

- **Denormalization**: Data stored in multiple places (source records + weekly aggregates)
- **Consistency**: Relies on signals to keep aggregates in sync
- **Storage**: Additional table with ~52 bytes per week per student
- **Week boundary logic**: Must handle ISO week calculations correctly

### Storage Estimate

- **Per record**: ~52 bytes
- **Per student per year**: ~2.7 KB (52 weeks)
- **1000 students × 1 year**: ~2.7 MB
- **Negligible overhead** compared to performance benefits

### Mitigation

- Signals ensure automatic updates
- Recalculation methods can be called manually if needed
- Backfill command available for data fixes
- Database indexes ensure fast queries

## Edge Cases Handled

### 1. Weeks with Only Quizzes or Only Assignments
- If only quizzes exist: `overall_average = quiz_average`
- If only assignments exist: `overall_average = assignment_average`
- If neither exists: `overall_average = None`

### 2. Weeks with No Data
- Record may exist with `null` averages
- Dashboard can filter out or display as "No data"
- Record created when first quiz/assignment in that week

### 3. Multiple Attempts Per Week
- All attempts included in average calculation
- Count reflects total number of attempts
- Weighted average ensures accurate representation

### 4. Teacher-Graded Quizzes
- Uses `final_score` property if available
- Falls back to auto-calculated `score`
- Handled transparently in aggregation

### 5. Assignment Grading Date vs Submission Date
- Prefers `graded_at` when available
- Falls back to `submitted_at` if not graded yet
- Ensures accurate week assignment

## Maintenance

### Manual Recalculation

If weekly aggregates become out of sync, they can be manually recalculated:

```python
from users.models import StudentWeeklyPerformance

# Recalculate specific week
weekly_perf = StudentWeeklyPerformance.objects.get(
    student_profile=student_profile,
    year=2024,
    week_number=5
)
weekly_perf.recalculate_week_averages()

# Recalculate all weeks for a student
weekly_perfs = StudentWeeklyPerformance.objects.filter(
    student_profile=student_profile
)
for wp in weekly_perfs:
    wp.recalculate_week_averages()
```

### Monitoring

Check `updated_at` timestamp to verify aggregates are being updated:
- Should update whenever a quiz/assignment is completed in that week
- If timestamp is stale, investigate signal handlers

### Troubleshooting

**Weekly aggregates not updating:**
1. Check if signals are registered in `users/apps.py`
2. Verify signal handlers in `users/signals.py`
3. Check Django logs for signal errors
4. Verify `completed_at` or `graded_at` dates are set correctly

**Incorrect values:**
1. Run backfill command to recalculate all weekly aggregates
2. Verify source data (QuizAttempt, AssignmentSubmission) is correct first
3. Check for edge cases (zero quizzes/assignments, null scores, etc.)
4. Verify week calculation logic (ISO week format)

**Missing weeks:**
1. Weeks are only created when a quiz/assignment is completed
2. If no activity in a week, no record exists (this is expected)
3. Use backfill command to create records for historical weeks with data

## Future Enhancements

Potential improvements:
- Add monthly/quarterly aggregates for longer-term trends
- Add course-specific weekly breakdowns
- Add comparison with class average or previous periods
- Add trend indicators (improving/declining/stable)
- Add caching layer for even faster queries
- Add admin action to recalculate selected weeks
- Add API endpoint for custom date ranges
- Add export functionality for performance reports

## Related Files

- `users/models.py` - Model definition and helper methods
- `users/signals.py` - Signal handlers for automatic updates
- `users/apps.py` - Signal registration
- `users/admin.py` - Admin interface configuration
- `users/management/commands/backfill_weekly_performance.py` - One-time backfill command
- `users/migrations/0005_*.py` - Database migration
- `student/views.py` - Dashboard view integration

## Summary

This implementation provides efficient, automatically-maintained weekly performance aggregates for the parent dashboard. The separate model approach ensures fast queries while maintaining data consistency through signal-based updates. The ISO week format provides standardized week boundaries, and the weighted average approach ensures accurate representation of student performance over time.

