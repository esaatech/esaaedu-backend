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

**Course structure:** Each course has lessons grouped by **modules**; after every module there is a **test**. So: Module 1 (lessons) → Test → Module 2 (lessons) → Test → …

**Core flow (re-emphasised):**

- A student is enrolled in **one class per course** — one enrollment → one Class.
- Get the **last ClassEvent** (past) for that class.
  - **If there is no last event** (e.g. brand-new class): **schedule the first lesson**.
- **If last event was a lesson:**
  - Check that lesson’s **quiz** (StudentLessonProgress / QuizAttempt) and **assignment** (AssignmentSubmission) are completed.
  - If that lesson is the **last lesson in its module** → schedule the **module test**.
  - Otherwise → schedule the **next lesson**.
- **If last event was a test:**
  - Check the **lesson before the test** (the last lesson of that module) for quiz and assignment completed.
  - Then schedule the **next lesson** (first lesson of the next module).
- **Before scheduling:** Only schedule when the **next class/event is less than 24 hours away** (in the student’s timezone). If the next class is more than 24h away, do not schedule yet (skip or defer).
- From that, decide: **schedule** (next class &lt; 24h and requirements met), **remind** (requirements not met), or **skip** (e.g. next class &gt; 24h away).

| Task | Status |
|------|--------|
| Add `tutorx/scheduling/` with helpers: timezones at local hour 0, students in those timezones | Done (`SchedulingChecker.get_timezones_at_midnight`, `get_students_in_timezones`) |
| Core flow: student → enrollment → class (one per course) → last ClassEvent | Done (`get_class_for_enrollment`, `get_last_class_event`) |
| If no last event: schedule first lesson | Done (`get_next_schedulable_event` → first_lesson) |
| If last event is a lesson: check that lesson’s quiz and assignment; if last in module → schedule test, else → schedule next lesson | Done (`is_lesson_requirements_met`, `is_lesson_last_in_module`, `get_next_schedulable_event`) |
| If last event is a test: check the lesson before the test (last lesson of module); then schedule next lesson (first of next module) | Done (`get_lesson_before_test`, `get_next_schedulable_event`) |
| Before scheduling: ensure next class is **&lt; 24 hours away** (student timezone); if not, do not schedule | Done (`is_next_event_within_24h`) |
| Management command `run_scheduling_checks`: run flow, log/return “schedule” vs “remind” vs “skip” | Done (`python manage.py run_scheduling_checks`) |
| Run command every hour (cron / Cloud Scheduler) | Pending (deploy) |

**Implementation:** `tutorx/scheduling/services.py` defines **`SchedulingChecker`** with one method per task. Entry point: `tutorx/management/commands/run_scheduling_checks.py`.

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

- **Course structure:** Lessons are grouped by modules; after every module there is a test (Module → lessons → Test → next Module → …).
- **One class per course:** A student is enrolled in exactly one class per course. Enrollment → that class.
- **No last event:** If the class has no past ClassEvent yet, schedule the first lesson.
- **Last event = lesson:** Check that lesson’s quiz/assignment. If it’s the last lesson in the module → schedule the **module test**. Otherwise → schedule the **next lesson**.
- **Last event = test:** Check the **lesson before the test** (last lesson of that module) for quiz/assignment; then schedule the **next lesson** (first lesson of next module).
- **24h rule (before scheduling):** Only schedule when the next class is **less than 24 hours away**, using the student’s timezone. If the next class is more than 24h away, do not schedule (skip or defer until a later run).
- **Timezones:** Store IANA names on `StudentProfile.timezone`; hourly job only processes students whose local hour is 0.
