# Enrollment schedules for self-paced courses

## Overview

Self-paced courses (`Course.delivery_type = self_paced`) do not require picking a shared live Class at enroll time. Each enrollment can store a **cadence** (`EnrollmentSchedule`) — daily or weekly, with optional clock time — and the backend generates upcoming `ClassEvent`s so Continue Learning and the student calendar still work.

Live and hybrid courses keep the existing class-picker flow at enroll.

**Frontend doc:** `little-learners-tech/docs/self-paced-course-schedule.md`

---

## Enrollment (no shared class)

When `course.delivery_type == 'self_paced'`:

- **Free / trial:** `POST /api/courses/student/enroll-free/<course_id>/` — `class_id` optional (omit).
- **Paid:** Stripe payment intent + `POST /api/billing/courses/<course_id>/confirm-enrollment/` — `class_id` optional for self-paced only; still required for live/hybrid.

Implementation:

- `courses/views.py` — `student_enroll_course` / enroll-free (optional `class_id`)
- `student/utils.py` — `complete_enrollment_without_stripe(..., class_id=None)` OK
- `billings/views.py` — `ConfirmEnrollmentView`, `complete_enrollment_process`, webhooks: skip class join when `class_id` absent and course is self-paced

`delivery_type` is exposed on student dashboard recommended/dropped course payloads and `FrontendCourseSerializer` for the enroll modal.

Personal `Class` for generated events is created when the user **saves** a schedule (not at enroll).

---

## Models

### `Course.delivery_type` (existing)

`live` | `self_paced` | `hybrid` (default `live`). On teacher course serializers and create/update.

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
| `start_time` / `end_time` | required when repeating weekly/daily and not all_day |
| `horizon_days` | legacy; generation is lesson-driven |
| `class_instance` | private Class for this enrollment's generated events |
| `timezone` | IANA string (e.g. `America/Denver`); sent by frontend on save |

---

## APIs

### List self-paced enrollments

`GET /api/student/self-paced-schedules/`

- Student/parent: own active self-paced enrollments
- Teacher: `?student_id=<StudentProfile.id>`

### Get / set schedule

`GET|PUT|PATCH /api/student/enrolled-courses/<enrollment_id>/schedule/`

**Weekly pattern (repeat until course ends — default):**

```json
{
  "frequency": "weekly",
  "repeat_weekly": true,
  "weekdays": [0, 2, 4],
  "all_day": false,
  "start_time": "09:00:00",
  "end_time": "10:00:00",
  "timezone": "America/Denver"
}
```

**Per-week custom slots (`repeat_weekly: false`):**

```json
{
  "frequency": "weekly",
  "repeat_weekly": false,
  "weekdays": [],
  "custom_slots": [
    {"date": "2026-07-21", "start_time": "09:00:00", "end_time": "10:00:00"}
  ],
  "all_day": false,
  "timezone": "America/Denver"
}
```

- Allowed: course teacher, enrolled student, parent (student credentials / parent_email)
- Rejects if `delivery_type != self_paced`
- On save: validates cadence, ensures personal Class, deletes **future** `is_schedule_generated` events, creates lesson `ClassEvent`s for incomplete lessons

Response includes `events_generated`.

Student schedule API (`GET /api/student/schedule/`) includes `all_day` on events.

---

## Generation rules

Service: `student/services/enrollment_schedule.py` → `regenerate_schedule_events()`

- **Lesson-driven:** slots until incomplete lessons are placed (not fixed `horizon_days`)
- **Daily:** every day from today (in scheduler timezone)
- **Weekly + repeat:** matching `weekdays` from today onward
- **Weekly + custom_slots:** one lesson per slot in date order (today+ only)
- Completed lessons skipped; course lesson order preserved
- Past generated events not deleted

---

## Timezone

Wall-clock values on the cadence are interpreted in `EnrollmentSchedule.timezone`. The frontend sends `Intl.DateTimeFormat().resolvedOptions().timeZone` on save. Event generation uses `_resolve_schedule_tz()` so Class Schedule displays the same local time as when the user picked the slot (same idea as live class scheduling via ISO datetimes).

---

## Frontend (reference)

- Schedule tabs: Class Schedule | Course Schedule
- Editor: week/day time grid (1h slots), repeat-weekly checkbox, mobile drill-in list → editor
- See `little-learners-tech/docs/self-paced-course-schedule.md`

---

## Migrations

- `courses.0070_classsession_all_day_classevent_all_day`
- `student.0021_classsession_all_day_enrollment_schedule`
- `student.0022_enrollment_schedule_repeat_weekly_custom_slots`
