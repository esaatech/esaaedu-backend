# Staff weekly calendar APIs

## Endpoints

- `GET /api/teacher/staff/calendar/week/?start_date=YYYY-MM-DD&tz=IANA_NAME`
- `GET /api/teacher/staff/classes/<class_id>/dialog/`
- `GET /api/teacher/staff/teachers/<teacher_id>/dialog/`
- `GET /staff/calendar/` (staff weekly page)

## Weekly response

- Includes `week_start`, `week_end`, `timezone`, and `results[]`.
- Each event row provides: course, class, teacher, `start_at`, `end_at`, and status.
- Status values:
  - `scheduled` (session matched an event)
  - `not_scheduled` (weekly timetable slot without matching event)
  - `event_only` (event exists without direct timetable slot match)

Schema: `teacher/schemas/staff_week_calendar_response.schema.json`

### Overlapping and horizontally clustered events (UI)

- When multiple events on the same day start within **30 minutes** of each other, they are clustered and rendered side‑by‑side in the weekly grid.
- Each cluster shares a single vertical band (based on the earliest start and latest end in that cluster), and events are given equal horizontal width within that band.
- On hover, the focused event expands to fill the full horizontal width of the day column so its title and metadata remain readable and clickable even in dense schedules.
- Event chips enforce a readable minimum height so short-duration events can still display full key content (time, class, course, teacher).
- Teacher name in each chip is bold and clickable; clicking it opens a reusable teacher detail dialog.

## Class dialog response

- Returns class identity and `dialog_html` rendered from reusable template partial.
- `dialog_html` comes from `templates/staff/calendar/_class_detail_body.html`.

Schema: `teacher/schemas/staff_class_dialog_response.schema.json`

## Teacher dialog response

- Returns teacher identity and `dialog_html` rendered from reusable teacher detail partial.
- `dialog_html` comes from `templates/staff/calendar/_teacher_detail_body.html`, which includes the shared teacher detail template.

Schema: `teacher/schemas/staff_teacher_dialog_response.schema.json`
