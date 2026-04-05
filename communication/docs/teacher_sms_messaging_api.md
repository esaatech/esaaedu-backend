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
| `target_phone` | string | No | **E.164 (or raw digits normalized server-side).** When set, the SMS is sent to this number **only if** it matches the student profile’s **`child_phone` or `parent_phone`** after normalization. Omit to keep legacy behavior: send to child phone if set, otherwise parent phone. |

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
| `403` | Not a teacher; student not in class for this course; multiple classes match and `class_id` omitted; no shared class (when no ids sent); **`target_phone` is not one of the student’s allowed profile phones**. |
| `404` | Student, class, or course not found. |
| `503` | Twilio not configured on the server. |

---

## Recommended UI flow

1. `GET /api/teacher/message-templates/?channel=sms`
2. User selects a template.
3. From your course context, read **`course_title`** (e.g. `Course.title` for the selected course).
4. `message = body_template.format(course_title=course_title, student_name=studentFirstName)` (include only allowed placeholders).
5. `POST /api/teacher/sms/send/` with `{ student_user_id, message, course_id }` (use `class_id` as well if you need to disambiguate). Optionally include `target_phone` when the UI explicitly chose child vs parent so the destination matches the selected recipient.

---

## Inbound SMS (Twilio webhook — reference only)

Inbound rows are stored on `SmsRoutingLog` with `direction=inbound` and `inbound_routing`:

- `pending` — just received; routing not finished.
- `routed` — correlated to a prior **outbound** to the same student/from number (reply thread); `teacher`, `course`, and `course_class` may be filled from that outbound.
- `generic_admin` — no matching prior outbound; treat as generic/admin handling.

---

## Admin

Templates are edited in **Django Admin** → **Communication** → **Message templates** (no deploy required for copy changes).

---

## 3. Per-enrollment SMS unread (teacher students master)

The Student Management roster does **not** use a separate SMS-count API per row. Counts are included on **`GET /api/courses/teacher/students/master/`** for each object in **`students[]`**:

| Field | Type | Meaning |
|-------|------|--------|
| `sms_unread_count` | int | Unread inbound `SmsRoutingLog` rows for this teacher, this **course** (`SmsRoutingLog.course_id` matches the enrollment’s course), and `student_phone` matching normalized **`child_phone`** or **`parent_phone`** on `users.StudentProfile`. |
| `student_sms_unread_count` | int | Present when child and parent numbers differ: count for the child line only. |
| `parent_sms_unread_count` | int | Present when child and parent numbers differ: count for the parent line only. |

If child and parent normalize to the **same** E.164 number, only **`sms_unread_count`** is returned (no split), so the client does not double-count.

**Attribution rules:** Inbound rows must be tied to a **course** on the log (typically after reply correlation copies `course_id` from the prior outbound). Inbound SMS with no course remains **excluded** from these per-row totals.

**Implementation:** `communication/services/teacher_roster_sms.py` (`build_teacher_sms_unread_pair_counts`, `sms_unread_fields_for_enrollment`), called from `courses.views.teacher_students_master`.

**Global badge (unchanged):** `GET /api/teacher/sms/unread-count/` returns `total_unread` for all unread inbound SMS for the teacher (see `TeacherSmsUnreadCountView`).

---

## 4. Outbound thread (SMS first; email/WhatsApp reserved)

Teacher UI can list SMS history for a student line (same phone + Twilio number as send), optionally scoped by `course_id`.

### `GET /api/teacher/students/<student_user_id>/outbound-thread/`

| Query | Required | Description |
|-------|----------|-------------|
| `channel` | No (default `sms`) | `sms` returns thread; `email` / `whatsapp` → `501` with `{ "detail": "not_implemented", "thread": [] }`. |
| `recipient_type` | No (default `student`) | `parent` \| `student` — which profile line to use when `target_phone` is omitted (same as messaging panel). |
| `course_id` | No | UUID; when set, only logs with this `SmsRoutingLog.course_id` are returned. |
| `class_id` | No | UUID; disambiguation (same rules as send SMS). |
| `target_phone` | No | When set, must match normalized `child_phone` or `parent_phone` for that student. |

**200** body:

```json
{
  "channel": "sms",
  "thread": [
    {
      "id": "uuid",
      "direction": "inbound",
      "body": "…",
      "created_at": "2026-01-01T12:00:00+00:00",
      "read_at": null
    },
    {
      "id": "uuid",
      "direction": "outbound",
      "body": "…",
      "created_at": "2026-01-01T12:01:00+00:00",
      "delivery_status": "delivered",
      "delivery_error_code": ""
    }
  ]
}
```

**Implementation:** `communication/services/teacher_outbound_thread.py` + `TeacherStudentOutboundThreadView`.

### `POST /api/teacher/students/<student_user_id>/outbound-thread/mark-read/`

Marks **all** unread inbound rows in that thread (same match as GET) read. JSON body or query: same `channel`, `recipient_type`, `course_id`, `class_id`, `target_phone` as GET.

**200:** `{ "channel": "sms", "marked": <int> }` — number of rows updated.

Call when the teacher **opens the Inbox / thread view** so badges (`sms/unread-count`, master `sms_unread_count`) can drop after clients revalidate.

**501** for `channel=email` / `whatsapp` (not implemented).
