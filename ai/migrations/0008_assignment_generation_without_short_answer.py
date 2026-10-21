"""Stop the assignment generation base prompt from asking for short answers."""

from django.db import migrations


OLD_MIX = (
    "Create a mix of essay questions, fill-in-the-blank, and short answer "
    "questions with clear requirements."
)
NEW_MIX = (
    "Create a mix of essay questions and fill-in-the-blank questions with "
    "clear requirements.\n"
    "Use essay for every open written response, including brief ones."
)
SHORT_ANSWER_GUIDELINE = "- Short answer questions should be specific and answerable\n"
CLOSING = (
    "Do not create short answer questions. A brief written response is an essay."
)


def _rewrite(content: str) -> str:
    updated = (content or "").replace(OLD_MIX, NEW_MIX)
    updated = updated.replace(SHORT_ANSWER_GUIDELINE, "")
    if "short answer" in updated.lower() or "short_answer" in updated:
        updated = f"{updated.rstrip()}\n\n{CLOSING}"
    return updated


def drop_short_answer_from_assignment_prompt(apps, schema_editor):
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
    SystemInstruction.objects.filter(name=current.name, is_active=True).update(is_active=False)
    latest = SystemInstruction.objects.filter(name=current.name).order_by("-version").first()
    version = (latest.version if latest else 0) + 1
    new_instruction = SystemInstruction.objects.create(
        name=current.name,
        version=version,
        content=updated,
        description=(
            "Stop asking for short answer questions. Brief written responses are essays."
        ),
        is_active=True,
    )
    template.system_instruction = new_instruction
    template.save(update_fields=["system_instruction"])


class Migration(migrations.Migration):
    dependencies = [
        ("ai", "0007_courseteacherprompt"),
    ]

    operations = [
        migrations.RunPython(
            drop_short_answer_from_assignment_prompt,
            migrations.RunPython.noop,
        ),
    ]
