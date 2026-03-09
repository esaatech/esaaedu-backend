"""
Lesson chat handlers: one dedicated function per intent (explain_better, generate_questions, draw_explainer_image).

Each handler is called when the AI infers that intent; it uses lesson context and AI to produce the response.
Easier to debug: all handler entry points live here.
"""
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def handle_explain_better(
    lesson_context: str,
    phrase_or_concept: str,
    user_message: str = "",
) -> str:
    """
    Explain a phrase or concept from the lesson in simpler terms.
    Returns plain text (response_type: "text").
    """
    from .ai import TutorXAIService

    service = TutorXAIService()
    return service.explain_for_lesson_chat(
        lesson_context=lesson_context,
        phrase_or_concept=phrase_or_concept or "(the whole lesson or their question)",
        user_message=user_message,
    )


def handle_generate_questions(
    lesson_context: str,
    user_message: str = "",
) -> Dict[str, Any]:
    """
    Generate quiz-style questions from lesson content.
    Returns dict with "questions" and "message" (response_type: "qanda").
    """
    from .ai import TutorXAIService

    service = TutorXAIService()
    result = service.generate_questions_for_lesson_chat(
        lesson_context=lesson_context,
        user_message=user_message,
    )
    return {
        "questions": result.get("questions", []),
        "message": (result.get("message") or "Want to try more questions?").strip() or "Anything else I can help with?",
    }


def handle_draw_explainer_image(
    lesson_context: str,
    concept: str,
    user_message: str = "",
) -> Dict[str, Any]:
    """
    Generate image description and prompt for an explainer/diagram.
    Returns dict with "image_description" and "image_prompt" (response_type: "explainer_image").
    """
    from ai.gemini_service import GeminiService
    from tutorx.schemas import get_draw_explainer_image_schema

    system = (
        "You are a tutor. Based on the lesson content, produce a short image description (for accessibility) "
        "and a detailed prompt suitable for an image generation API to illustrate the concept. "
        "Lesson content:\n" + (lesson_context[:8000] if lesson_context else "")
    )
    prompt = f"Concept to illustrate: {concept or user_message or 'the main idea of the lesson'}"
    schema = get_draw_explainer_image_schema()
    response = GeminiService().generate(
        system_instruction=system,
        prompt=prompt,
        response_schema=schema,
        temperature=0.5,
    )
    parsed = response.get("parsed") or {}
    return {
        "image_description": parsed.get("image_description", ""),
        "image_prompt": parsed.get("image_prompt", ""),
    }
