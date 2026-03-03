# Lead Magnet App

Lead magnet guides: PDF + preview image stored in GCP, optional Brevo list and welcome email on submission. The app is **standalone**: with this documentation you can move the app to another Django project and implement the frontend from scratch.

## Overview

- **Models**: `LeadMagnet` (guide with slug, title, description, benefits, PDF/preview paths and URLs, Brevo list/template IDs, `email_only_delivery` flag) and `LeadMagnetSubmission` (first name, email, FK to guide).
- **Storage**: PDF and preview image are uploaded from Django Admin and stored in GCP at `lead_magnets/{slug}/guide.pdf` and `lead_magnets/{slug}/preview.<ext>` using the project’s `default_storage` (GCS when configured).
- **Brevo**: Optional. On submit, the contact can be added to a list and a welcome email (with PDF link) can be sent using a Brevo template or default HTML. The app uses the **Brevo Python SDK** (`brevo-python`) when available, with a **requests** fallback.
- **email_only_delivery**: Per-guide checkbox in admin. When set, the frontend should use a different CTA label (e.g. "Send me the guide") and must not open/download the PDF after submit—delivery is by email only. When unset, "Download Now" with instant download is allowed.

## API Endpoints

Base path: **`/api/lead-magnet/`**. All endpoints are public (`AllowAny`).

### Get guide (public)

**`GET /api/lead-magnet/<slug>/`**

Returns public data for an active lead magnet. Includes **guide_url**: the full frontend URL for this guide (uses the saved slug), e.g. `https://www.sbtyacademy.com/guide/30-steam-activities`.

**Response** (200):

```json
{
  "title": "Guide Title",
  "description": "Guide description text.",
  "benefits": ["Benefit 1", "Benefit 2"],
  "preview_image_url": "https://storage.googleapis.com/...",
  "guide_url": "https://www.sbtyacademy.com/guide/30-steam-activities",
  "email_only_delivery": false
}
```

- **email_only_delivery** (boolean): When `true`, the frontend should use a different primary CTA label (e.g. "Send me the guide") and must not open or download the PDF after submit; the guide is delivered by email only. When `false`, show "Download Now" and allow instant download using `pdf_url` after submit.

**Errors**: 404 if slug not found or guide is inactive.

---

### Submit (capture lead)

**`POST /api/lead-magnet/<slug>/submit/`**

**Content-Type**: `application/json`

**Body**:

```json
{
  "first_name": "Jane",
  "email": "jane@example.com"
}
```

**Behavior**:

- Creates or updates a `LeadMagnetSubmission` for this guide and email (one submission per email per guide).
- If the guide has `brevo_list_id` (or `BREVO_LIST_ID` is set), adds/updates the contact in Brevo and adds to that list.
- If the guide has a `pdf_url`, sends a welcome email with the PDF link (via Brevo transactional email or template).

**Response** (201 created / 200 already submitted):

```json
{
  "success": true,
  "message": "Thank you! Check your email for the guide.",
  "pdf_url": "https://storage.googleapis.com/.../guide.pdf"
}
```

When the guide has **email_only_delivery** set to `true`, the backend returns **pdf_url** as an empty string `""` so the frontend does not offer an instant download.

**Errors**: 400 if `first_name` or `email` missing/invalid; 404 if slug not found or guide inactive.

---

## Frontend instructions: email_only_delivery

Use the following behavior so the lead-magnet page matches the backend.

### 1. Fetch guide data

- Call **GET /api/lead-magnet/<slug>/** when loading the guide page (e.g. by slug from the URL).
- Store the full response. You need **email_only_delivery** (boolean) and the rest (title, description, benefits, preview_image_url, guide_url) for the UI.

### 2. Button label

- If **email_only_delivery === true**: Use a label that reflects email delivery only, e.g. **"Send me the guide"** or **"Get the guide"**. Do not use "Download Now".
- If **email_only_delivery === false**: Keep the current label, e.g. **"Download Now"**.

### 3. After submit (POST /api/lead-magnet/<slug>/submit/)

- Always show the success message from the response, e.g. **"Thank you! Check your email for the guide."**
- **If email_only_delivery === true** (from the GET response you already have): Do **not** open the PDF in a new tab and do **not** trigger a file download. Do not use `pdf_url` from the submit response (the backend will return `pdf_url: ""` anyway).
- **If email_only_delivery === false**: If the submit response includes a non-empty **pdf_url**, open it in a new tab and/or trigger a download (current behavior).

### 4. Summary

| email_only_delivery (from GET) | Button label example   | On submit success                          |
|--------------------------------|------------------------|--------------------------------------------|
| `true`                          | "Send me the guide"    | Show message only; do not open/download PDF |
| `false`                         | "Download Now"         | Show message and open/download PDF if pdf_url present |

The backend does not require any new headers or query params; use the same GET and POST requests as before.

---

## Frontend integration (standalone)

This section describes how to implement the lead-magnet page in any frontend (React, Vue, plain JS, etc.) so the feature works end-to-end. Use it when adding the lead magnet to this project or when moving the app to another project.

### Route and URL

- **Frontend route**: One page per guide, e.g. `/guide/:slug` or `/guide/<slug>`. The slug is the same as the backend (e.g. `30-steam-activities`). The full guide URL is `{LEAD_MAGNET_GUIDE_BASE_URL}/guide/{slug}` (e.g. `https://www.sbtyacademy.com/guide/30-steam-activities`).
- **Backend base**: GET and POST go to the same host as the API, e.g. `https://your-api.com/api/lead-magnet/`.

### Page load

1. Read the slug from the URL (e.g. from the route param).
2. Call **GET /api/lead-magnet/<slug>/**.
3. If 404, show a "Guide not found" (or redirect). If 200, store the response: `title`, `description`, `benefits`, `preview_image_url`, `guide_url`, **`email_only_delivery`** (boolean).

### Page content

- **Header**: e.g. "Free Download: {title}".
- **Body**: Render `description`, optionally `benefits` as a list, and optionally `preview_image_url` as an image.
- **Form**: **First Name** (text, required), **Email** (email, required), **Submit button** (label depends on `email_only_delivery`—see below).
- **Success state**: After a successful submit, show the success message and, only when `email_only_delivery` is false, optionally open or download the PDF using `pdf_url` from the submit response.

### Button label (from GET response)

- **email_only_delivery === true**: Use a label like **"Send me the guide"** or **"Get the guide"** (do not use "Download Now").
- **email_only_delivery === false**: Use **"Download Now"** (or keep your current label).

### Submit flow

1. On form submit, send **POST /api/lead-magnet/<slug>/submit/** with JSON body: `{ "first_name": "<value>", "email": "<value>" }`. Use **Content-Type: application/json**.
2. **On success** (201 or 200): Show `response.message`. If **email_only_delivery** (from the GET response) is **false** and `response.pdf_url` is non-empty, open the PDF in a new tab and/or trigger a download (e.g. `window.open(response.pdf_url)`). If **email_only_delivery** is **true**, do not open or download the PDF; the backend returns `pdf_url: ""` anyway.
3. **On error** (400/404): Show validation or not-found message as appropriate.

### Example flow (pseudocode)

```
On mount:
  guide = GET /api/lead-magnet/{slug}/
  if 404 -> show "Not found"
  else -> set state: guide (title, description, benefits, preview_image_url, guide_url, email_only_delivery)

Button label:
  guide.email_only_delivery ? "Send me the guide" : "Download Now"

On form submit:
  res = POST /api/lead-magnet/{slug}/submit/ with { first_name, email }
  if error -> show error
  else:
    show res.message
    if !guide.email_only_delivery && res.pdf_url -> open or download res.pdf_url
```

### CORS

- The API must allow requests from the frontend origin (e.g. Django `CORS_ALLOWED_ORIGINS`). No auth is required for GET or POST.

### Summary: frontend contract

| Source | Field / moment | Use |
|--------|----------------|-----|
| GET /api/lead-magnet/<slug>/ | title, description, benefits, preview_image_url, guide_url | Page content and optional preview. |
| GET | email_only_delivery | Button label; whether to open/download PDF after submit. |
| POST .../submit/ | success, message | Always show message. |
| POST | pdf_url | Only use when email_only_delivery is false and pdf_url is non-empty; then open or download. |

---

## Django Admin

- **Lead magnets** (`/admin/lead_magnet/leadmagnet/`): Add/edit guides. Fields:
  - **Slug**, **Title**, **Description**, **Benefits**, **Is active**.
  - **Guide URL**: After save, shows the full frontend link (e.g. `https://www.sbtyacademy.com/guide/30-steam-activities`) with a **Copy** button (on the change form). On the list view, each row has a **Guide URL** column with the same URL and a **Copy** button so you can copy without opening the record.
  - **Files**: Upload PDF and preview image; they are saved to GCP and paths/URLs are stored automatically.
  - **Brevo**: **List ID** (optional; or use `BREVO_LIST_ID` in .env as default). **Template ID** (optional; use a Brevo transactional template for the welcome email; params: `FIRSTNAME`, `PDF_URL`, `GUIDE_TITLE`).
  - **Email only delivery**: When checked, the frontend should show a different button label (e.g. "Send me the guide") and must not open or download the PDF after submit—delivery is by email only.
- **Submissions** (`/admin/lead_magnet/leadmagnetsubmission/`): View submissions per guide.

Deleting a `LeadMagnet` removes its PDF and preview files from GCP before deleting the record.

## Settings (optional)

1. **Install the Brevo SDK** (recommended):  
   `poetry add brevo-python` or `pip install brevo-python`.  
   If the SDK is not installed, the app falls back to HTTP requests (no extra dependency).

2. **Add your Brevo API key to Django**  
   Get the key from [Brevo → Settings → API Keys](https://app.brevo.com/settings/keys/api).  
   In your `.env` file add:
   ```bash
   BREVO_API_KEY=xkeysib-your-key-here
   ```
   Do not commit the key; keep it in `.env` (and ensure `.env` is in `.gitignore`). In `.env`, put comments on their own line—inline comments (e.g. `BREVO_LIST_ID=4 # comment`) can be read as part of the value and break integer parsing.

3. **Optional** (for welcome emails): set `BREVO_SENDER_EMAIL` and, if you use a list, `BREVO_LIST_ID` or set `brevo_list_id` per guide in admin.

In `backend/settings.py` these are read via `config()`:

| Variable | Description |
|----------|-------------|
| `BREVO_API_KEY` | Brevo API key (required for list add + welcome email). Get from Brevo → Settings → API Keys. |
| `BREVO_SENDER_EMAIL` | From address for welcome emails. |
| `BREVO_SENDER_NAME` | From name (default: "Little Learners Tech"). |
| `BREVO_LIST_ID` | Default list ID if a guide has no `brevo_list_id`. |
| `BREVO_WELCOME_TEMPLATE_ID` | Optional Brevo template ID for welcome email (params: `FIRSTNAME`, `PDF_URL`, `GUIDE_TITLE`). |
| `LEAD_MAGNET_GUIDE_BASE_URL` | Base URL for the frontend guide page (default: `https://www.sbtyacademy.com`). Full guide URL = `{base}/guide/{slug}`. |

GCP uses existing backend config: `GCS_BUCKET_NAME`, `GCS_PROJECT_ID`, and credentials (e.g. `GOOGLE_APPLICATION_CREDENTIALS`).

## URL wiring

In the project root `urls.py`:

```python
path("api/lead-magnet/", include('lead_magnet.urls')),
```

App URLs:

- `<slug:slug>/` → guide detail (GET)
- `<slug:slug>/submit/` → submit (POST)

---

## Reusing this app in another project

To use the lead_magnet app in another Django project:

1. **Copy the app**: Copy the `lead_magnet` directory (including `docs/`, migrations, and all modules) into the new project.
2. **Install**: Add `'lead_magnet'` to `INSTALLED_APPS` and run migrations. Ensure the project has a working `default_storage` (e.g. GCP) if you use PDF/preview uploads.
3. **URLs**: In the project root `urls.py`, add: `path("api/lead-magnet/", include('lead_magnet.urls'))`.
4. **Settings**: Configure Brevo (see [Settings (optional)](#settings-optional)) and, if needed, `LEAD_MAGNET_GUIDE_BASE_URL` for the frontend guide base URL.
5. **Frontend**: Implement the guide page using the [Frontend integration (standalone)](#frontend-integration-standalone) section above (route, GET guide, form, POST submit, button label and post-submit behavior). No backend code changes are required beyond wiring and settings.
