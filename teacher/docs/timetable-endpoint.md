# Teacher Timetable Endpoint

## Overview

This endpoint returns a lean, fixed weekly timetable payload for teacher-owned classes.

- Endpoint: `GET /api/teacher/timetable/`
- Auth: `IsAuthenticated` (teacher only)
- Source of truth: `Class` + active `ClassSession`
- Purpose: support weekly template rendering and future calendar export features

This is intentionally separate from `GET /api/teacher/schedule/`, which returns dated and flexible `ClassEvent` items.

## Response shape

```json
{
  "classes": [
    {
      "class_id": "uuid",
      "class_name": "Morning Group A",
      "course_id": "uuid",
      "course_title": "Scratch Coding",
      "timezone": "Africa/Lagos",
      "sessions": [
        {
          "id": "uuid",
          "session_number": 1,
          "day_of_week": 0,
          "day_name": "Monday",
          "start_time": "10:00:00",
          "end_time": "11:00:00",
          "is_active": true
        }
      ]
    }
  ],
  "summary": {
    "total_courses": 2,
    "total_classes": 5,
    "total_slots": 14
  }
}
```

## Files

- URL registration: `teacher/urls.py`
- View: `teacher/views.py` (`TeacherTimetableAPIView`)
- Serializers: `teacher/serializers.py`
  - `TeacherTimetableSessionSerializer`
  - `TeacherTimetableClassSerializer`
  - `TeacherTimetableResponseSerializer`

## Notes

- Includes only active classes and active sessions.
- Keeps timetable/template concerns separate from schedule/event concerns.
- Suitable foundation for future ICS/Google/Outlook export functionality.
