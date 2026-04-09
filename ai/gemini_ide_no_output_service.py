"""
GeminiIdeNoOutputExplainService — why a successful run produced no visible prints / empty output area.

System instruction: AIPromptTemplate `ide_no_output_explanation`.
"""
import logging
from typing import Any, Dict, Optional, Tuple

from ai.gemini_service import GeminiService

logger = logging.getLogger(__name__)

IDE_NO_OUTPUT_TEMPLATE_NAME = "ide_no_output_explanation"

FALLBACK_SYSTEM_INSTRUCTION = """You are a patient coding tutor for children and beginners.

The student's program finished without an error, but they see little or nothing in the output area.
Infer skill level only from their code. Explain in Markdown why there might be no visible prints
(missing print(), wrong branch, only defining functions/classes, etc.). Mention turtle or graphics
only if the code suggests it. Do not invent errors. Prefer small concrete checks over full solutions."""


class GeminiIdeNoOutputExplainService:
    """Explains missing stdout after a successful run; system prompt from DB template."""

    def __init__(self) -> None:
        self.gemini_service = GeminiService()

    def _get_system_instruction_and_config(self) -> Tuple[str, float, Optional[str]]:
        try:
            from ai.models import AIPromptTemplate

            template = AIPromptTemplate.objects.filter(
                name=IDE_NO_OUTPUT_TEMPLATE_NAME,
                is_active=True,
            ).first()
            if template and template.system_instruction:
                content = (template.default_system_instruction or "").strip()
                if content:
                    model_name = (template.model_name or "").strip() or None
                    return content, float(template.temperature), model_name
        except Exception as e:
            logger.warning("Failed to load IDE no-output AIPromptTemplate: %s", e, exc_info=True)

        return FALLBACK_SYSTEM_INSTRUCTION, 0.45, None

    def _build_input_message(
        self,
        *,
        language: str,
        code: str,
        observed_output: str = "",
        lesson_title: str = "",
        course_title: str = "",
        grade_level: str = "",
    ) -> str:
        blocks = [
            "Programming language:",
            language.strip() or "(unknown)",
        ]
        if course_title and course_title.strip():
            blocks.extend(["", "Course title (optional context):", course_title.strip()])
        if lesson_title and lesson_title.strip():
            blocks.extend(["", "Lesson or snippet title (optional context):", lesson_title.strip()])
        if grade_level and grade_level.strip():
            blocks.extend(["", "Declared grade level (optional):", grade_level.strip()])
        blocks.extend(
            [
                "",
                "Student code:",
                code,
                "",
                "What the IDE showed in the output area after the run (may be empty or a placeholder):",
                observed_output if observed_output is not None else "",
            ]
        )
        return "\n".join(blocks)

    def explain(
        self,
        *,
        language: str,
        code: str,
        observed_output: str = "",
        lesson_title: str = "",
        course_title: str = "",
        grade_level: str = "",
    ) -> Dict[str, Any]:
        system_instruction, temperature, model_name = self._get_system_instruction_and_config()
        prompt = self._build_input_message(
            language=language,
            code=code,
            observed_output=observed_output or "",
            lesson_title=lesson_title or "",
            course_title=course_title or "",
            grade_level=grade_level or "",
        )
        response = self.gemini_service.generate(
            system_instruction=system_instruction,
            prompt=prompt,
            temperature=temperature,
            max_tokens=None,
            model_name=model_name,
        )
        return {
            "explanation": (response.get("raw") or "").strip(),
            "model": response.get("model") or "",
        }
