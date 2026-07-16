# Newsletter subscribe API

Public endpoint that captures an email, stores it locally, and adds the contact to the Brevo **newsletter** list. Welcome emails and campaigns are handled in Brevo (list automation / campaigns), not by this endpoint.

## Setup

1. In Brevo, create a list (e.g. "Newsletter").
2. Copy the list ID into env:

```bash
BREVO_NEWSLETTER_LIST_ID=123
BREVO_API_KEY=...
```

3. Optional: in Brevo, create an automation: *Contact added to Newsletter list → send welcome email*.

4. Run migrations:

```bash
python manage.py migrate home
```

## Endpoint

**`POST /api/home/newsletter/subscribe/`**

Public (`AllowAny`).

**Body:**

```json
{
  "email": "jane@example.com",
  "first_name": "Jane",
  "source": "homepage"
}
```

| Field | Required | Notes |
|-------|----------|--------|
| `email` | Yes | Normalized to lowercase |
| `first_name` | No | Stored + sent to Brevo as `FIRSTNAME` |
| `source` | No | e.g. `homepage`, `blog_post` |

**Response (201 new / 200 already subscribed):**

```json
{
  "message": "You're subscribed! Check your inbox for a welcome email soon.",
  "subscribed": true,
  "already_subscribed": false,
  "brevo_synced": true
}
```

If `BREVO_NEWSLETTER_LIST_ID` is missing, the email is still saved locally and `brevo_synced` is `false`.
