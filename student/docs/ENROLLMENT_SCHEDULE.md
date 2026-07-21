# Enrollment schedules for self-paced courses (Phase 1)

## Overview

Self-paced courses (`Course.delivery_type = self_paced`) do not require picking a shared live Class at enroll time. Instead each enrollment can store a **cadence** (`EnrollmentSchedule`) — daily or weekly, with optional clock time — and the backend generates upcoming `ClassEvent`s so Continue Learning and the student calendar still work.

Live courses keep the existing class-picker flow.

## Models

### `Course.delivery_type` (existing)

Exposed on teacher course list/detail/create-update serializers: `live` | `self_paced` | `hybrid` (default `live`).

### `ClassSession`

- `all_day` (bool, default False)
- `start_time` / `end_time` nullable when `all_day=True`

### `ClassEvent`

- `all_day` — date-based event (no clock focus)
- `is_schedule_generated` — True when created from an EnrollmentSchedule regenerate

### `EnrollmentSchedule` (`student.models`)

OneToOne on `EnrolledCourse`:

| Field | Notes |
|-------|--------|
| `frequency` | `daily` \| `weekly` |
| `weekdays` | JSON list `0=Mon .. 6=Sun` (when `repeat_weekly`) |
| `repeat_weekly` | default True — one week pattern repeats until lessons end |
| `custom_slots` | when not repeating: `[{date, start_time, end_time}, …]` |
| `all_day` | default True (daily); weekly calendar picks use clock times |
| `start_time` / `end_time` | required when repeating and not all_day |
| `horizon_days` | legacy; generation is lesson-driven |
| `class_instance` | private Class created for this child's generated events |
| `timezone` | optional IANA string |

## APIs

### List self-paced enrollments

`GET /api/student/self-paced-schedules/`

- Student/parent (student credentials): own active self-paced enrollments
- Teacher: pass `?student_id=<StudentProfile.id>` for students in their courses

### Get / set schedule

`GET|PUT|PATCH /api/student/enrolled-courses/<enrollment_id>/schedule/`

**PUT body example (daily, no time):**

```json
{
  "frequency": "daily",
  "weekdays": [],
  "all_day": true,
  "horizon_days": 21
}
```

**Weekly pattern (repeat until course ends — default):**

```json
{
  "frequency": "weekly",
  "repeat_weekly": true,
  "weekdays": [0, 2, 4],
  "all_day": false,
  "start_time": "09:00:00",
  "end_time": "10:00:00"
}
```

**Per-week custom slots (checkbox off):**

```json
{
  "frequency": "weekly",
  "repeat_weekly": false,
  "weekdays": [],
  "custom_slots": [
    {"date": "2026-07-21", "start_time": "09:00:00", "end_time": "10:00:00"},
    {"date": "2026-07-23", "start_time": "14:00:00", "end_time": "15:00:00"}
  ],
  "all_day": false
}
```

- Allowed: course teacher, enrolled student, parent linked by student credentials / parent_email
- Rejects if `delivery_type != self_paced`
- On save: creates/updates cadence, ensures a personal Class, deletes **future** `is_schedule_generated` events, creates new lesson ClassEvents for incomplete lessons

Response includes `events_generated` (count created).

## Frontend (Phase 2)

- Shared editor: `src/components/dashboard/schedule/SelfPacedScheduleEditor.tsx`
- **Schedule page tabs:** **Class Schedule** (calendar) | **Course Schedule** (master–detail)
- Course Schedule master list + detail editor: `CourseScheduleMasterDetail.tsx`
- **Daily:** one lesson per day until remaining lessons are done
- **Weekly / pick days:** month calendar — click a day to toggle that weekday; optional time; pattern continues until the course ends (no per-week setup, no plan-ahead field)
- Saving regenerates ClassEvents and refreshes the Class Schedule calendar
- Student schedule API events include `all_day`; FullCalendar renders them in the all-day slot

## Generation rules

- Slots continue until **all incomplete lessons** are placed (lesson-driven; not a fixed horizon)
- Daily = every day; weekly = matching `weekdays` only
- One incomplete lesson per slot (course order); completed lessons skipped
- Past generated events are not deleted
- `horizon_days` on the model is unused for generation (kept for compatibility)

## Migrations

- `courses.0070_classsession_all_day_classevent_all_day`
- `student.0021_enrollment_schedule`

## Timezone

Cadence `start_time` / `end_time` / `custom_slots` are **wall-clock** values in `EnrollmentSchedule.timezone` (IANA, e.g. `America/Denver`). The frontend sends `Intl.DateTimeFormat().resolvedOptions().timeZone` on save. Event generation uses that zone so Class Schedule shows the same local time as when the parent picked the slot (same idea as class scheduling via ISO datetimes).
