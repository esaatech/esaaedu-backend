# Scheduling automation – phased plan

Track progress here. Hourly job runs at “midnight” per student timezone: check last class (quiz/assignment done), then either schedule next class (< 24h) or remind student + parent.

---

## Phase 1: Foundation (timezone + exposure)

**Goal:** Every student has a timezone and it can be set/read.

| Task | Status |
|------|--------|
| Add `StudentProfile.timezone` field and migration | Done |
| Run migration: `python manage.py migrate users` | |
| Expose timezone in API (e.g. student profile/settings GET and PATCH) | |
| Expose timezone in Django Admin (StudentProfile) | Done |
| (Optional) Validator or allowed IANA list for frontend dropdown | Done |

**Exit criteria:** Students can have a timezone set via app or admin; backend can read it.

---

## Phase 2: Scheduling job and “midnight” logic

**Goal:** Hourly job runs and, for students in timezones where it’s local midnight, loads their class and last/next events and checks quiz/assignment (no side effects yet).

| Task | Status |
|------|--------|
| Add `tutorx/scheduling/` with helpers: timezones at local hour 0, students in those timezones | |
| Core flow: student → enrollment → single Class → last ClassEvent, next ClassEvent | |
| For last event’s lesson: check quiz completed (StudentLessonProgress / QuizAttempt) | |
| For last event’s lesson: check assignment completed (AssignmentSubmission) | |
| Management command `run_scheduling_checks`: run flow, log/return “schedule” vs “remind” vs “skip” | |
| Run command every hour (cron / Cloud Scheduler) | |

**Exit criteria:** Hourly run correctly identifies per student whether to “schedule” or “remind”; results are logged or inspectable.

---

## Phase 3: “Schedule the class” action

**Goal:** When the logic says “schedule” (next class < 24h and quiz/assignment done), perform the scheduling action.

| Task | Status |
|------|--------|
| Define what “schedule the class” means (e.g. calendar event, internal record, confirmation) | |
| Implement that action in `tutorx/scheduling/` (e.g. Calendar API or DB record) | |
| Call action from the command when flow returns “schedule” | |
| (Optional) Idempotency: student + event + date so no double-schedule | |

**Exit criteria:** For students who pass the check, the next class is actually scheduled when the job runs.

---

## Phase 4: Notifications (remind student + parent)

**Goal:** When the logic says “remind” (quiz/assignment not done), send a message to the student and to the parent.

| Task | Status |
|------|--------|
| Add notification layer (e.g. `tutorx/notifications/`): `send_reminder(student, parent_contact, template_key, context)` | |
| Send to student (email and/or in-app) | |
| Send to parent using `StudentProfile.parent_email` (and optionally `parent_phone`) | |
| Templates: student and parent “complete quiz/assignment before next class” | |
| From scheduling command, call notification when flow returns “remind” | |
| (Optional) Idempotency so same student isn’t spammed in same midnight window | |

**Exit criteria:** Students and parents receive the correct reminders when the job decides “remind”.

---

## Phase 5 (later): Attendance and hardening

**Goal:** Include attendance in the “ready for next class” check and harden the system.

| Task | Status |
|------|--------|
| For last ClassEvent date, check StudentAttendance (student, Class, date) | |
| Only “schedule” if quiz + assignment + attendance done; else “remind” | |
| Decide behavior when `StudentProfile.timezone` is empty (skip vs default) and document | |
| Log job runs, counts (schedule / remind / skip), and failures | |
| Rate limits / backoff for external APIs (email, calendar) if needed | |

**Exit criteria:** Attendance is part of the rule; defaults and monitoring in place.

---

## Summary

| Phase | Focus | Outcome |
|-------|--------|--------|
| **1** | Timezone on students + API + admin | Timezone set and readable |
| **2** | Hourly job + midnight filter + core logic (no side effects) | Per-student “schedule” vs “remind” decision |
| **3** | “Schedule the class” action | Next class actually scheduled when conditions pass |
| **4** | Notifications | Student and parent reminders when conditions fail |
| **5** | Attendance + defaults + monitoring | Stricter rules and production-ready behavior |

---

## Notes

- **One class per student:** Each enrollment has at most one Class (student in `Class.students`, same course).
- **Timezones:** Store IANA names on `StudentProfile.timezone`; hourly job only processes students whose local hour is 0.
- **24h rule:** “Next class < 24 hours away” uses the student’s timezone for comparison.
