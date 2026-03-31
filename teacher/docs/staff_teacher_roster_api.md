# Staff teacher roster APIs

## Endpoints

- `GET /api/teacher/staff/teachers/` — active teacher list (top-level only, fast).
- `GET /api/teacher/staff/teachers/<teacher_id>/` — selected teacher expanded detail (courses/classes/students).
- `GET /staff/teachers/?focus=<teacher_id>` — staff HTML page using reusable templates and lazy detail call.

## Permissions

Both APIs require `IsAuthenticated + IsAdminUser`.

## Query params (list)

- `q` (optional): search by teacher name/email.
- `focus` (optional): teacher user id; returned first in list to support focused page UX.

## Response contracts

- List item schema: `teacher/schemas/teacher_roster_list_item.schema.json`.
- Detail response is stable serializer shape from `teacher/roster_serializers.py` (`TeacherRosterDetailSerializer`).
- Operational list columns include `phone_number`, `next_pay_day`, and `pay_status` for quick payroll visibility.

## Design notes

- Top-level list keeps payload small for quick page load and agent calls.
- Detail endpoint is called lazily when a teacher row is opened.
- This mirrors a reusable tool contract for future orchestration without duplicating business logic.
