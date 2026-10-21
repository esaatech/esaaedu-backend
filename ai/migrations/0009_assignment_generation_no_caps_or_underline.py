"""Stop assignment prompts from asking for CAPS or underline."""

import re

from django.db import migrations

NEW_COMPUTER_FRIENDLY = """Computer-Friendly Requirement
	•	Since students complete assignments on a computer, do NOT ask them to circle answers.
	•	Use digital actions only, such as “type your answer” or “choose the correct option”.
	•	Do NOT tell students to write in CAPS or uppercase.
	•	Do NOT tell students to underline, circle, highlight, or mark text — they cannot do that in the app.
	•	Avoid any instructions that require physical writing tools.
"""

# Matches the Computer-Friendly block through the blank line before Tone (or EOF).
_COMPUTER_FRIENDLY_RE = re.compile(
    r"Computer-Friendly Requirement\s*"
    r"(?:.*\n)*?"
    r"(?=\s*Tone\b|\Z)",
    re.IGNORECASE,
)


def _rewrite(content: str) -> str:
    text = content or ""
    if not re.search(r"Computer-Friendly Requirement", text, re.IGNORECASE):
        return text
    # Preserve CRLF if the stored prompt uses it.
    newline = "\r\n" if "\r\n" in text else "\n"
    replacement = NEW_COMPUTER_FRIENDLY.replace("\n", newline)
    if not replacement.endswith(newline):
        replacement = replacement.rstrip("\r\n") + newline + newline
    updated, count = _COMPUTER_FRIENDLY_RE.subn(replacement, text, count=1)
    if count == 0:
        return text
    return updated


def strip_caps_and_underline_from_assignment_prompt(apps, schema_editor):
    AIPromptTemplate = apps.get_model("ai", "AIPromptTemplate")
    SystemInstruction = apps.get_model("ai", "SystemInstruction")
    template = AIPromptTemplate.objects.filter(name="assignment_generation").first()
    if template is None or not template.system_instruction_id:
        return
    current = SystemInstruction.objects.filter(pk=template.system_instruction_id).first()
    if current is None:
        return
    updated = _rewrite(current.content or "")
    if updated == (current.content or ""):
        return
    SystemInstruction.objects.filter(name=current.name, is_active=True).update(
        is_active=False
    )
    latest = (
        SystemInstruction.objects.filter(name=current.name)
        .order_by("-version")
        .first()
    )
    version = (latest.version if latest else 0) + 1
    new_instruction = SystemInstruction.objects.create(
        name=current.name,
        version=version,
        content=updated,
        description=(
            "Remove CAPS/underline student instructions; treat them as do-nots "
            "for digital fill-in-the-blank and typed answers."
        ),
        is_active=True,
    )
    template.system_instruction = new_instruction
    template.save(update_fields=["system_instruction"])


class Migration(migrations.Migration):
    dependencies = [
        ("ai", "0008_assignment_generation_without_short_answer"),
    ]

    operations = [
        migrations.RunPython(
            strip_caps_and_underline_from_assignment_prompt,
            migrations.RunPython.noop,
        ),
    ]
