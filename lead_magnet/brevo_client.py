"""
Brevo (Sendinblue) client for lead magnet: add contact to list and send welcome email.
Uses the official Brevo Python SDK (brevo-python) when available; falls back to requests.
"""
import requests
from django.conf import settings

BREVO_API_BASE = "https://api.brevo.com/v3"

# Optional: use Brevo SDK (pip install brevo-python)
try:
    from brevo import Brevo
    from brevo.core.api_error import ApiError
    BREVO_SDK_AVAILABLE = True
except ImportError:
    Brevo = None
    ApiError = Exception
    BREVO_SDK_AVAILABLE = False


def _get_api_key():
    return getattr(settings, "BREVO_API_KEY", None) or ""


def _get_client():
    """Return a Brevo client instance if API key and SDK are available."""
    if not BREVO_SDK_AVAILABLE or not Brevo:
        return None
    api_key = _get_api_key()
    if not api_key:
        return None
    return Brevo(api_key=api_key, timeout=15.0)


def add_contact_to_list(email: str, first_name: str, list_id: int) -> bool:
    """
    Create or update contact in Brevo and add to the given list.
    Uses Brevo SDK when available; otherwise uses requests.
    Returns True on success, False otherwise.
    """
    api_key = _get_api_key()
    if not api_key:
        print("[Brevo] BREVO_API_KEY not set; skipping add to list")
        return False

    client = _get_client()
    print(f"[Brevo] add_contact_to_list: email={email} list_id={list_id} api_key_set={bool(api_key)} sdk={client is not None}")
    if client and hasattr(client, "contacts"):
        try:
            # Brevo SDK v4: create_contact(email=, attributes=, list_ids=, update_enabled=)
            client.contacts.create_contact(
                email=email,
                attributes={"FIRSTNAME": first_name},
                list_ids=[list_id],
                update_enabled=True,
            )
            print(f"[Brevo] Contact {email} added/updated and added to list {list_id}")
            return True
        except Exception as e:
            err_str = str(e).lower()
            print(f"[Brevo] create_contact exception: {e}")
            if "400" in err_str or "already" in err_str or "duplicate" in err_str:
                try:
                    # Brevo SDK v4: add_contact_to_list(list_id, request=...)
                    client.contacts.add_contact_to_list(list_id, request={"emails": [email]})
                    print(f"[Brevo] Contact {email} added to list {list_id} (fallback)")
                    return True
                except Exception as add_e:
                    print(f"[Brevo] add_contact_to_list failed: {add_e}")
            return False

    # Fallback: requests
    print("[Brevo] Using requests fallback for add_contact_to_list")
    try:
        create_url = f"{BREVO_API_BASE}/contacts"
        create_payload = {
            "email": email,
            "attributes": {"FIRSTNAME": first_name},
            "listIds": [list_id],
            "updateEnabled": True,
        }
        headers = {"api-key": api_key, "Content-Type": "application/json"}
        r = requests.post(create_url, json=create_payload, headers=headers, timeout=15)
        if r.status_code in (201, 204):
            print(f"[Brevo] Contact {email} added/updated and added to list {list_id} (requests)")
            return True
        if r.status_code == 400:
            add_url = f"{BREVO_API_BASE}/contacts/lists/{list_id}/contacts/add"
            add_r = requests.post(add_url, json={"emails": [email]}, headers=headers, timeout=15)
            if add_r.status_code in (201, 204):
                print(f"[Brevo] Contact {email} added to list {list_id} (requests fallback)")
                return True
        print(f"[Brevo] add contact/list failed: {r.status_code} {r.text}")
        return False
    except Exception as e:
        print(f"[Brevo] add_contact_to_list request failed: {e}")
        return False


def send_welcome_email(
    to_email: str,
    first_name: str,
    pdf_url: str,
    guide_title: str,
    *,
    template_id: int | None = None,
) -> bool:
    """
    Send welcome email with PDF link.
    Uses Brevo SDK when available; otherwise uses requests.
    Returns True on success, False otherwise.
    """
    api_key = _get_api_key()
    if not api_key:
        print("[Brevo] BREVO_API_KEY not set; skipping welcome email")
        return False

    sender_email = getattr(settings, "BREVO_SENDER_EMAIL", None) or ""
    sender_name = getattr(settings, "BREVO_SENDER_NAME", "") or "Little Learners Tech"
    if not sender_email:
        print("[Brevo] BREVO_SENDER_EMAIL not set; skipping welcome email")
        return False

    print(f"[Brevo] send_welcome_email: to={to_email} sender={sender_email} api_key_set={bool(api_key)}")

    html_content = (
        f"<p>Hi {first_name},</p>\n"
        f"<p>Thanks for your interest in <strong>{guide_title}</strong>.</p>\n"
        f'<p>Download your guide here: <a href="{pdf_url}">{pdf_url}</a></p>\n'
        "<p>Best,<br/>Little Learners Tech</p>"
    )

    template_id = template_id or getattr(settings, "BREVO_WELCOME_TEMPLATE_ID", None)

    client = _get_client()
    if client and hasattr(client, "transactional_emails") and hasattr(client.transactional_emails, "send_transac_email"):
        try:
            # When using a template: only template_id + params (and sender, to). No subject/html_content — template controls those.
            if template_id:
                print(f"[Brevo] Sending welcome email using Brevo template_id={template_id} (params: FIRSTNAME, PDF_URL, GUIDE_TITLE)")
                client.transactional_emails.send_transac_email(
                    sender={"name": sender_name, "email": sender_email},
                    to=[{"email": to_email, "name": first_name}],
                    template_id=template_id,
                    params={"FIRSTNAME": first_name, "PDF_URL": pdf_url, "GUIDE_TITLE": guide_title},
                )
            else:
                client.transactional_emails.send_transac_email(
                    sender={"name": sender_name, "email": sender_email},
                    to=[{"email": to_email, "name": first_name}],
                    subject=f"Your guide: {guide_title}",
                    html_content=html_content,
                )
            print(f"[Brevo] Welcome email sent to {to_email} for guide {guide_title}")
            return True
        except Exception as e:
            print(f"[Brevo] send email (SDK) failed: {e}")
            return False

    # Fallback: requests
    print("[Brevo] Using requests fallback for send_welcome_email")
    try:
        payload = {
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": to_email, "name": first_name}],
        }
        if template_id:
            payload["templateId"] = template_id
            payload["params"] = {
                "FIRSTNAME": first_name,
                "PDF_URL": pdf_url,
                "GUIDE_TITLE": guide_title,
            }
        else:
            payload["subject"] = f"Your guide: {guide_title}"
            payload["htmlContent"] = html_content
        r = requests.post(
            f"{BREVO_API_BASE}/smtp/email",
            json=payload,
            headers={"api-key": api_key, "Content-Type": "application/json"},
            timeout=15,
        )
        if r.status_code in (201, 200):
            print(f"[Brevo] Welcome email sent to {to_email} for guide {guide_title} (requests)")
            return True
        print(f"[Brevo] send email failed: {r.status_code} {r.text}")
        return False
    except Exception as e:
        print(f"[Brevo] send_welcome_email request failed: {e}")
        return False


def on_lead_magnet_submit(guide, email: str, first_name: str) -> None:
    """
    Helper to run when a user submits the lead magnet form (name + email to download).
    Adds the contact to the Brevo list (if configured) and sends the welcome email with PDF link.
    Call this from your download/submit view after saving the submission.
    """
    list_id = getattr(guide, "brevo_list_id", None) or getattr(settings, "BREVO_LIST_ID", None)
    pdf_url = getattr(guide, "pdf_url", None) or ""
    print(f"[Brevo] on_lead_magnet_submit: guide={getattr(guide, 'slug', '?')} list_id={list_id} pdf_url={'set' if pdf_url else '(empty)'}")
    if list_id:
        add_contact_to_list(email=email, first_name=first_name, list_id=list_id)
    else:
        print("[Brevo] No list_id (brevo_list_id or BREVO_LIST_ID); skipping add to list")
    if pdf_url:
        template_id = getattr(guide, "brevo_template_id", None) or getattr(settings, "BREVO_WELCOME_TEMPLATE_ID", None)
        send_welcome_email(
            to_email=email,
            first_name=first_name,
            pdf_url=pdf_url,
            guide_title=guide.title,
            template_id=template_id,
        )
    else:
        print("[Brevo] No pdf_url on guide; skipping welcome email")