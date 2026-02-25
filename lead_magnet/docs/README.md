# Lead Magnet App

Lead magnet guides: PDF + preview image stored in GCP, optional Brevo list and welcome email on submission.

## Overview

- **Models**: `LeadMagnet` (guide with slug, title, description, benefits, PDF/preview paths and URLs, Brevo list ID) and `LeadMagnetSubmission` (first name, email, FK to guide).
- **Storage**: PDF and preview image are uploaded from Django Admin and stored in GCP at `lead_magnets/{slug}/guide.pdf` and `lead_magnets/{slug}/preview.<ext>` using the project’s `default_storage` (GCS when configured).
- **Brevo**: Optional. On submit, the contact can be added to a list and a welcome email with the PDF link can be sent (see settings below).

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
  "guide_url": "https://www.sbtyacademy.com/guide/30-steam-activities"
}
```

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

**Errors**: 400 if `first_name` or `email` missing/invalid; 404 if slug not found or guide inactive.

## Django Admin

- **Lead magnets** (`/admin/lead_magnet/leadmagnet/`): Add/edit guides. Set slug, title, description, benefits; upload PDF and preview image (saved to GCP); set optional `brevo_list_id` and `is_active`. After save, **Guide URL** shows the full frontend link (e.g. `https://www.sbtyacademy.com/guide/30-steam-activities`) with a **Copy** button. Paths and URLs are filled automatically after upload.
- **Submissions** (`/admin/lead_magnet/leadmagnetsubmission/`): View submissions per guide.

Deleting a `LeadMagnet` removes its PDF and preview files from GCP before deleting the record.

## Settings (optional)

In `.env` or `backend/settings.py` (via `config()`):

| Variable | Description |
|----------|-------------|
| `BREVO_API_KEY` | Brevo API key (required for list add + welcome email). |
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
