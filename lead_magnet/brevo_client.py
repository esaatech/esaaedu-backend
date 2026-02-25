"""
Brevo (Sendinblue) client for lead magnet: add contact to list and send welcome email.
"""
import logging
import requests

from django.conf import settings

logger = logging.getLogger(__name__)

BREVO_API_BASE = "https://api.brevo.com/v3"


def add_contact_to_list(email: str, first_name: str, list_id: int) -> bool:
    """
    Create or update contact in Brevo and add to the given list.
    Returns True on success, False otherwise.
    """
    api_key = getattr(settings, "BREVO_API_KEY", None) or ""
    if not api_key:
        logger.warning("BREVO_API_KEY not set; skipping add to list")
        return False

    # Create or update contact
    create_url = f"{BREVO_API_BASE}/contacts"
    create_payload = {
        "email": email,
        "attributes": {"FIRSTNAME": first_name},
        "listIds": [list_id],
        "updateEnabled": True,
    }
    headers = {"api-key": api_key, "Content-Type": "application/json"}

    try:
        r = requests.post(create_url, json=create_payload, headers=headers, timeout=15)
        if r.status_code in (201, 204):
            logger.info("Brevo: contact %s added/updated and added to list %s", email, list_id)
            return True
        # If contact exists, try adding to list only
        if r.status_code == 400:
            add_url = f"{BREVO_API_BASE}/contacts/lists/{list_id}/contacts/add"
            add_r = requests.post(
                add_url,
                json={"emails": [email]},
                headers=headers,
                timeout=15,
            )
            if add_r.status_code in (201, 204):
                logger.info("Brevo: contact %s added to list %s", email, list_id)
                return True
        logger.warning("Brevo add contact/list failed: %s %s", r.status_code, r.text)
        return False
    except Exception as e:
        logger.exception("Brevo request failed: %s", e)
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
    Send welcome email with PDF link. Uses template if BREVO_WELCOME_TEMPLATE_ID
    is set and template supports params; otherwise sends simple HTML.
    Returns True on success, False otherwise.
    """
    api_key = getattr(settings, "BREVO_API_KEY", None) or ""
    if not api_key:
        logger.warning("BREVO_API_KEY not set; skipping welcome email")
        return False

    sender_email = getattr(settings, "BREVO_SENDER_EMAIL", None) or ""
    sender_name = getattr(settings, "BREVO_SENDER_NAME", "") or "Little Learners Tech"
    if not sender_email:
        logger.warning("BREVO_SENDER_EMAIL not set; skipping welcome email")
        return False

    template_id = template_id or getattr(settings, "BREVO_WELCOME_TEMPLATE_ID", None)
    url = f"{BREVO_API_BASE}/smtp/email"
    headers = {"api-key": api_key, "Content-Type": "application/json"}

    html_content = (
        f"<p>Hi {first_name},</p>\n"
        f"<p>Thanks for your interest in <strong>{guide_title}</strong>.</p>\n"
        f"<p>Download your guide here: <a href=\"{pdf_url}\">{pdf_url}</a></p>\n"
        "<p>Best,<br/>Little Learners Tech</p>"
    )

    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": to_email, "name": first_name}],
        "subject": f"Your guide: {guide_title}",
    }

    if template_id:
        payload["templateId"] = template_id
        payload["params"] = {
            "FIRSTNAME": first_name,
            "PDF_URL": pdf_url,
            "GUIDE_TITLE": guide_title,
        }
    else:
        payload["htmlContent"] = html_content

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code in (201, 200):
            logger.info("Brevo: welcome email sent to %s for guide %s", to_email, guide_title)
            return True
        logger.warning("Brevo send email failed: %s %s", r.status_code, r.text)
        return False
    except Exception as e:
        logger.exception("Brevo send email failed: %s", e)
        return False
