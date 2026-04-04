# Staff SMS inbox (Django UI + session APIs)

Staff and superusers use a browser inbox to triage admin-queue SMS, teacher-routed threads, delivery issues, and to compose outbound SMS. Everything under **`/staff/messages/`** uses **session authentication** (logged-in Django admin/staff), not Firebase.

---

## Page and URLs

| | |
|---|---|
| **Inbox page** | `GET /staff/messages/` — `StaffMessagesInboxPageView` |
| **API base** | `/api/communication/staff/messages/` (included from `backend/urls.py`) |

Optional query params on the page: `log=<uuid>` (open a thread on load), `bucket=` (reserved for list focus).

---

## Authentication

- All JSON endpoints: **`SessionAuthentication`** + **`IsAuthenticated`** + **`IsAdminUser`**.
- Call from the same browser session as the staff login (cookies). No Bearer token.

---

## Contact display names (`contact_display_name`)

Thread rows and log detail include a **`contact_display_name`** string when the thread’s **`student_phone`** can be matched to a profile phone number.

- **Resolution** is **read-time** only (no extra DB columns). Implemented in **`communication/services/staff_contact_display.py`**:
  - Builds a map of canonical **E.164 → label** from **`StudentProfile`** (`child_phone` / `parent_phone` with child or parent labels), **`ParentProfile.phone_number`**, and **`TeacherProfile.phone_number`**.
  - **`lookup_display_name`** uses **`phone_match_candidates`** plus **last-10-digit** fallback when formatting differs slightly.
- If nothing matches, **`contact_display_name`** is an **empty string**; the UI still shows the raw phone.

---

## Endpoints (summary)

### `GET .../admin-unread/`

Query: `recent_limit` (1–50, default 10).

Response:

- **`unread_threads`**, **`recent_threads`**: arrays of thread summary objects. Each includes **`student_phone`**, **`twilio_number`**, **`unread_count`**, **`has_unread`**, **`last_activity_at`**, **`preview`**, **`default_log_id`**, and **`contact_display_name`**.

### `GET .../teacher-unread/`

Query: `recent_offset`, `recent_limit` (1–50).

Response: **`unread_threads`**, **`recent_threads`**, **`recent_has_more`**, **`recent_offset`**, **`recent_limit`**, **`next_recent_offset`**, plus **`contact_display_name`** on each thread row.

### `GET .../delivery-issues/`

Query: `limit` (1–100).

Response: **`issues`** (rows include **`contact_display_name`** when resolvable), **`recent_outbound_delivery`**.

### `GET .../logs/<uuid:log_id>/`

Loads the anchor log, marks matching inbounds read, returns:

```json
{
  "log": {
    "id": "...",
    "student_phone": "+1...",
    "contact_display_name": "Optional resolved name",
    "...": "..."
  },
  "thread": [ ... ]
}
```

### `GET .../contacts/`

Flat directory for the compose **+** picker.

Query: **`q`** (optional search), **`limit`** (default 500, max 600).

Response:

```json
{
  "entries": [
    {
      "user_id": 1,
      "display": "Full name or email",
      "email": "...",
      "role": "student",
      "phone": "+1...",
      "phone_key": "...",
      "phone_label": "e.g. Student (child phone)"
    }
  ]
}
```

### `GET .../users/search/`

Typeahead for compose (min **2** chars in **`q`**). Returns **`results`** with **`id`**, **`email`**, **`role`**, **`display`**, **`phones`**.

### `POST .../send/`

Staff outbound / reply. Modes include **`reply`** (`log_id`, `message`) and **`compose_phone`** (`to_phone`, `message`), plus user-targeted compose modes as implemented in **`StaffMessagesSendApiView`**.

---

## Frontend behavior (inbox template)

Templates live under **`templates/staff/messages/`** (notably **`inbox_page.html`** and **`partials/detail_reply.html`**).

- **Thread list rows** show **`contact_display_name`** beside the phone when present (e.g. `Name · +1…`).
- **Thread & reply** header shows the same resolved name (from log detail) under the section title when available.
- **Contacts modal**: opening **+** shows the full modal layout immediately (title, search, A–Z rail skeleton, loading spinner), then fills the list when **`GET .../contacts/`** completes. Search refetch dims the list briefly instead of emptying it first.
- Modal **Close** uses a compact width in the header (not full-width secondary button styling).

---

## Tests

**`communication.tests.StaffMessagesApiTests`** covers admin thread list and log detail **`contact_display_name`** when a profile phone matches the log line.

---

## Related code

| Area | Module |
|------|--------|
| Views / routes | `communication/staff_messages_views.py`, `communication/staff_urls.py` |
| Thread summaries, contacts directory | `communication/services/staff_sms_ui.py` |
| E.164 → display label | `communication/services/staff_contact_display.py` |
| Phone helpers | `communication/services/phone.py` |
