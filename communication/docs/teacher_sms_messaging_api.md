# Teacher SMS & message templates — frontend API contract

Use this document (and the JSON mirror below) to implement the teacher messaging UI.

**Live JSON contract (same content, structured):** `GET /api/docs/teacher-sms-messaging/`

---

## Authentication

- Send the usual **Firebase ID token** (or your app’s auth) as `Authorization: Bearer <token>`.
- Both endpoints require an authenticated user with role **teacher**.

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
| `class_id` | UUID string | No* | Class UUID. *Strongly recommended:* ensures the teacher teaches that class, the student is enrolled, and enables server-side SMS branding. |

### Success `201` body

```json
{
  "id": "uuid-of-sms-routing-log",
  "twilio_message_sid": "SMxxxxxxxx",
  "student_phone": "+1XXXXXXXXXX"
}
```

### Server-side SMS prefix

If `class_id` is present, the backend may prepend something like:

`[SBTY Academy - {Class.name}] {Teacher name}: ` + your `message`.

So template text should focus on **course** wording (e.g. `{course_title}`); avoid repeating long “SBTY Academy” lines in the template.

### Common errors

| Status | Meaning |
|--------|---------|
| `400` | Missing `student_user_id` / `message`, bad UUID, bad student id type, student has no phone on profile, etc. |
| `403` | Not a teacher, or teacher/student/class permission failure. |
| `404` | Student or class not found. |
| `503` | Twilio not configured on the server. |

---

## Recommended UI flow

1. `GET /api/teacher/message-templates/?channel=sms`
2. User selects a template.
3. From the current class context, read **`course_title`** (e.g. `class.course.title` from your existing class API).
4. `message = body_template.format(course_title=course_title)` (add any other keys from `variables`).
5. `POST /api/teacher/sms/send/` with `{ student_user_id, message, class_id }`.

---

## Admin

Templates are edited in **Django Admin** → **Communication** → **Message templates** (no deploy required for copy changes).
