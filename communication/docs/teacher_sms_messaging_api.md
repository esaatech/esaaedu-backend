# Teacher SMS & message templates — frontend API contract

Use this document (and the JSON mirror below) to implement the teacher messaging UI.

**Live JSON contract (same content, structured):** `GET /api/docs/teacher-sms-messaging/`

---

## Authentication

- Send the usual **Firebase ID token** (or your app’s auth) as `Authorization: Bearer <token>`.
- All teacher messaging endpoints require an authenticated user with role **teacher**.

---

## 1. List message templates

Fetch preset copy for SMS (or other channels later).

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/teacher/message-templates/` |

### Query parameters

| Name | Required | Default | Values |
|------|----------|---------|--------|
| `channel` | No | `sms` | `sms`, `email`, `whatsapp` |

### Success `200` body

```json
{
  "channel": "sms",
  "templates": [
    {
      "slug": "class-started",
      "label": "Course has started",
      "body_template": "Hello from SBTY Academy — just to let you know that {course_title} has started. We're glad to have you with us!",
      "subject_template": null,
      "variables": ["course_title"]
    }
  ]
}
```

- **`slug`**: stable id for analytics or preselection.
- **`body_template`**: use **Python-style** placeholders (`{course_title}`). Substitute every name listed in **`variables`** before sending SMS.
- **`subject_template`**: for `channel=email` later; `null` for SMS.

### Allowed SMS placeholders (fixed)

- `{course_title}` - resolved to the selected course title.
- `{student_name}` - resolved to the student first name.

Unknown placeholders are rejected at template save time in admin/API.

### Errors

- **`403`**: `{ "error": "Only teachers can list message templates" }`
- **`400`**: invalid `channel` value.

---

## 2. Send SMS (Twilio)

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `/api/teacher/sms/send/` |
| **Content-Type** | `application/json` |

### Request body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `student_user_id` | integer | Yes | Target student’s `User.id` (`role` must be `student`). |
| `message` | string | Yes | **Final** body after you applied template placeholders (this is the “inner” message). |
| `course_id` | UUID string | No* | **`courses.Course` primary key** — preferred when the UI is filtered by course (e.g. Student Management). Teacher must own the course; the student must be on exactly **one** of that teacher’s classes for that course, unless you also send `class_id`. |
| `class_id` | UUID string | No* | **`courses.Class` primary key** — optional; use for legacy clients or to disambiguate when multiple classes match the same course + student. If both `course_id` and `class_id` are sent, the class must belong to that course. |

\*At least one of `course_id` or `class_id` is **recommended** so the server can attach course context to the log and brand the SMS. If **neither** is sent, the server still allows send when the teacher shares **any** class with the student (first match used for logging and branding).

**Important:** Do **not** send `EnrolledCourse.id` or any other UUID here — only `Course.id` or `Class.id`.

### Success `201` body

```json
{
  "id": "uuid-of-sms-routing-log",
  "twilio_message_sid": "SMxxxxxxxx",
  "student_phone": "+1XXXXXXXXXX"
}
```

### SMS body as sent

Twilio receives **`message` exactly as you send it** after template substitution. The server does **not** prepend teacher name, course title, or an extra “SBTY Academy” line — your template and UI copy are the full SMS.

`course_id` / `class_id` are still used for **permission checks** and **logging** (`SmsRoutingLog`), not to alter the message text.

### Common errors

| Status | Meaning |
|--------|---------|
| `400` | Missing `student_user_id` / `message`, bad UUID, `class_id` not matching `course_id`, etc. |
| `403` | Not a teacher; student not in class for this course; multiple classes match and `class_id` omitted; no shared class (when no ids sent). |
| `404` | Student, class, or course not found. |
| `503` | Twilio not configured on the server. |

---

## 3. Inbound SMS unread count (badges)

| | |
|---|---|
| **Method** | `GET` |
| **URL** | `/api/teacher/sms/inbound/unread-count/` |

### Success `200` body

```json
{
  "unread_inbound_sms_count": 3
}
```

Counts `SmsRoutingLog` rows where `direction=inbound`, `teacher` is the current user, and `read_at` is null. Rows with `inbound_routing=generic_admin` have no teacher and are **not** included.

### Errors

- **`403`**: `{ "error": "Only teachers can access this endpoint" }`

---

## 4. Mark inbound SMS as read

| | |
|---|---|
| **Method** | `PATCH` |
| **URL** | `/api/teacher/sms/inbound/<log_id>/read/` |

`log_id` is the inbound `SmsRoutingLog` UUID (same as `id` from your list/detail source). The row must be **inbound** and assigned to the current teacher.

### Success `200` body

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "read_at": "2026-04-02T12:00:00.123456+00:00"
}
```

Calling again when already read returns the same `read_at` (idempotent).

### Errors

| Status | Meaning |
|--------|---------|
| `400` | `log_id` is not a valid UUID. |
| `403` | Not a teacher. |
| `404` | No such inbound log for this teacher (wrong id, outbound row, or another teacher’s row). |

---

## Recommended UI flow

1. `GET /api/teacher/message-templates/?channel=sms`
2. User selects a template.
3. From your course context, read **`course_title`** (e.g. `Course.title` for the selected course).
4. `message = body_template.format(course_title=course_title, student_name=studentFirstName)` (include only allowed placeholders).
5. `POST /api/teacher/sms/send/` with `{ student_user_id, message, course_id }` (use `class_id` as well if you need to disambiguate).
6. For inbound replies: use `GET /api/teacher/sms/inbound/unread-count/` for notification badges; when the teacher opens a message, `PATCH /api/teacher/sms/inbound/<uuid>/read/` so it stops counting as unread.

---

## Inbound SMS (Twilio webhook — reference only)

Inbound rows are stored on `SmsRoutingLog` with `direction=inbound` and `inbound_routing`:

- `pending` — just received; routing not finished.
- `routed` — correlated to a prior **outbound** to the same student/from number (reply thread), within `COMMUNICATION_SMS_REPLY_MAX_AGE_SECONDS` (default 1 hour); `teacher`, `course`, `course_class`, and `related_outbound` (FK to that outbound log) are set from the matched row.
- `generic_admin` — no matching prior outbound; treat as generic/admin handling.

**Read state:** For routed inbounds, `read_at` is null until the teacher calls the mark-read endpoint above; the UI can treat null as “notify / show badge.”

---

## Admin

Templates are edited in **Django Admin** → **Communication** → **Message templates** (no deploy required for copy changes).
