"""
GeminiIdeErrorExplainService — student-friendly IDE error explanations via Vertex AI.

System instruction is loaded from AIPromptTemplate `ide_error_explanation` (admin-editable).
The user message is only a fixed factual wrapper (language, code, error, optional context)
so pedagogy and level-matching rules live entirely in the system instruction.
"""
import logging
from typing import Any, Dict, Optional, Tuple

from ai.gemini_service import GeminiService

logger = logging.getLogger(__name__)

IDE_ERROR_TEMPLATE_NAME = "ide_error_explanation"

FALLBACK_SYSTEM_INSTRUCTION = """You are a patient coding tutor for children and beginners.

Infer the student's approximate level ONLY from the code they wrote (syntax, patterns, naming, structure).
Match your vocabulary and examples to that level. Do not teach advanced patterns (e.g. list comprehensions,
lambdas, decorators, async) unless the student's code already uses similar ideas.

Explain the error in clear Markdown: short intro, then numbered steps. Reference line numbers from the
error output when present. Be encouraging. Prefer hints that help them fix it themselves over pasting
a complete corrected program."""


class GeminiIdeErrorExplainService:
    """Explains IDE/runtime errors using Gemini; system prompt from DB template."""

    def __init__(self) -> None:
        self.gemini_service = GeminiService()

    def _get_system_instruction_and_config(self) -> Tuple[str, float, Optional[str]]:
        try:
            from ai.models import AIPromptTemplate

            template = AIPromptTemplate.objects.filter(
                name=IDE_ERROR_TEMPLATE_NAME,
                is_active=True,
            ).first()
            if template and template.system_instruction:
                content = (template.default_system_instruction or "").strip()
                if content:
                    model_name = (template.model_name or "").strip() or None
                    return content, float(template.temperature), model_name
        except Exception as e:
            logger.warning("Failed to load IDE error AIPromptTemplate: %s", e, exc_info=True)

        return FALLBACK_SYSTEM_INSTRUCTION, 0.5, None

    def _build_input_message(
        self,
        *,
        language: str,
        code: str,
        error_message: str,
        lesson_title: str = "",
        course_title: str = "",
        grade_level: str = "",
    ) -> str:
        """Factual payload only; no pedagogy (that stays in system_instruction)."""
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
                "Error or traceback from the runtime:",
                error_message,
            ]
        )
        return "\n".join(blocks)

    def explain(
        self,
        *,
        language: str,
        code: str,
        error_message: str,
        lesson_title: str = "",
        course_title: str = "",
        grade_level: str = "",
    ) -> Dict[str, Any]:
        if not error_message or not str(error_message).strip():
            raise ValueError("error_message is required")
        system_instruction, temperature, model_name = self._get_system_instruction_and_config()
        prompt = self._build_input_message(
            language=language,
            code=code,
            error_message=error_message,
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
