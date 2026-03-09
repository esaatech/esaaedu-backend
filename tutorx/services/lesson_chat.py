"""
Lesson chat: load and cache lesson context, AI-based intent inference, and dispatch.

TutorX lesson body is stored on courses.Lesson as tutorx_content (BlockNote JSON).
Context is cached by lesson_id. Intent is inferred by the model (function calling);
we dispatch to handlers in services/handlers.py (explain_better, generate_questions, draw_explainer_image).
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

CACHE_KEY_PREFIX = 'lesson_chat:'


def get_lesson_context(lesson_id):
    """
    Return lesson context string for the given lesson_id (title + body).
    Uses Django cache; key is lesson_chat:{lesson_id}, TTL from settings.
    For TutorX lessons the body is Lesson.tutorx_content (BlockNote JSON).
    """
    cache_key = f'{CACHE_KEY_PREFIX}{lesson_id}'
    ttl = getattr(settings, 'LESSON_CHAT_CACHE_TTL_SECONDS', 600)

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from courses.models import Lesson
    try:
        lesson = Lesson.objects.get(id=lesson_id)
    except Lesson.DoesNotExist:
        return None

    title = lesson.title or ''
    body = getattr(lesson, 'tutorx_content', '') or ''
    context = f"Lesson: {title}\n\n{body}".strip()

    cache.set(cache_key, context, timeout=ttl)
    logger.debug("Lesson context cached for lesson_id=%s (ttl=%ss)", lesson_id, ttl)
    return context


def invalidate_lesson_chat_cache(lesson_id) -> None:
    """
    Invalidate cached lesson context for this lesson_id.
    Call after saving lesson content (e.g. PUT /content/ or admin save) so chat sees updates immediately.
    """
    cache_key = f"{CACHE_KEY_PREFIX}{lesson_id}"
    cache.delete(cache_key)
    logger.debug("Lesson chat cache invalidated for lesson_id=%s", lesson_id)


def is_generate_questions_intent(message: str) -> bool:
    """
    Simple heuristic: treat as generate_questions when the user asks for questions/Q&A.
    Kept for fallback; primary intent is now AI-inferred via infer_intent().
    """
    if not message or not message.strip():
        return False
    lower = message.strip().lower()
    phrases = (
        "generate question",
        "generate questions",
        "give me question",
        "give me questions",
        "test my knowledge",
        "quiz me",
        "qanda",
        "q&a",
        "question and answer",
        "practice question",
        "practice questions",
    )
    return any(p in lower for p in phrases)


def _build_conversation_prompt(conversation: List[Dict[str, Any]], user_message: str) -> str:
    """Build prompt from recent conversation + new user message for intent model."""
    parts = []
    for msg in conversation[-6:]:  # last 3 turns
        role = msg.get("role", "")
        if role == "user":
            parts.append(f"Student: {msg.get('content', '')}")
        elif role == "assistant":
            content = msg.get("content") or (msg.get("data", {}).get("message") if msg.get("type") == "qanda" else "")
            if isinstance(content, str) and content:
                parts.append(f"Assistant: {content}")
            elif msg.get("type") in ("qanda", "explainer_image"):
                parts.append("Assistant: [structured response]")
    parts.append(f"Student: {user_message}")
    return "\n".join(parts)


def infer_intent(
    lesson_context: str,
    user_message: str,
    conversation: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Use AI with tool declarations to infer intent. Returns either
    {"function_call": {"name": str, "args": dict}} or {"text": str}.
    """
    from ai.gemini_service import GeminiService
    from tutorx.schemas import get_lesson_chat_tool_schemas_vertex

    system = (
        "You are a tutor assistant for a lesson. The student is asking something about the lesson content below. "
        "Based on their message, either call ONE of the provided tools (explain_better, generate_questions, draw_explainer_image) "
        "with the appropriate arguments, or respond with plain text if no tool fits (e.g. greeting or off-topic). "
        "When the student asks for a simpler explanation, doesn't understand something, or wants something explained like they're 5, call explain_better. "
        "When they ask for questions, quiz, Q&A, or to test their knowledge, call generate_questions. "
        "When they ask for a diagram, picture, or visual explanation, call draw_explainer_image.\n\n"
        "Lesson content:\n"
        + (lesson_context[:12000] if lesson_context else "(no content)")
    )
    prompt = _build_conversation_prompt(conversation or [], user_message)
    print("[Lesson chat intent] conversation prompt sent to AI:\n", prompt)
    print("[Lesson chat intent] --- end prompt ---")
    tool_schemas = get_lesson_chat_tool_schemas_vertex()
    service = GeminiService()
    result = service.generate_with_tools(
        system_instruction=system,
        prompt=prompt,
        tool_schemas=tool_schemas,
        temperature=0.2,
    )
    return result


def run_lesson_chat(
    lesson_context: str,
    user_message: str,
    conversation: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, Optional[str], Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Run AI-based intent inference and dispatch to the right handler.
    Returns (response_type, content_or_none, data_or_none, assistant_msg).
    assistant_msg is {"role": "assistant", "type": response_type, "content": ... and/or "data": ...}.
    """
    if not user_message or not user_message.strip():
        return "text", "Please type a message.", None, {"role": "assistant", "type": "text", "content": "Please type a message."}

    intent = infer_intent(lesson_context or "", user_message, conversation)

    if "function_call" in intent:
        name = intent["function_call"].get("name", "")
        args = intent["function_call"].get("args") or {}
        user_msg = args.get("user_message", user_message)

        if name == "explain_better":
            try:
                from .handlers import handle_explain_better
                phrase = args.get("phrase_or_concept") or user_message
                text = handle_explain_better(
                    lesson_context=lesson_context or "",
                    phrase_or_concept=phrase,
                    user_message=user_msg,
                )
                msg = {"role": "assistant", "type": "text", "content": text}
                return "text", text, None, msg
            except Exception as e:
                logger.warning("explain_better handler failed: %s", e)
                fallback = f"I couldn't explain that right now. ({e})"
                return "text", fallback, None, {"role": "assistant", "type": "text", "content": fallback}

        if name == "generate_questions":
            try:
                from .handlers import handle_generate_questions
                data = handle_generate_questions(
                    lesson_context=lesson_context or "",
                    user_message=user_msg,
                )
                msg = {"role": "assistant", "type": "qanda", "data": data}
                return "qanda", None, data, msg
            except Exception as e:
                logger.warning("generate_questions handler failed: %s", e)
                fallback = f"I couldn't generate questions right now. ({e})"
                return "text", fallback, None, {"role": "assistant", "type": "text", "content": fallback}

        if name == "draw_explainer_image":
            try:
                from .handlers import handle_draw_explainer_image
                concept = args.get("concept") or user_message
                data = handle_draw_explainer_image(
                    lesson_context=lesson_context or "",
                    concept=concept,
                    user_message=user_msg,
                )
                msg = {"role": "assistant", "type": "explainer_image", "data": data}
                return "explainer_image", None, data, msg
            except Exception as e:
                logger.warning("draw_explainer_image handler failed: %s", e)
                fallback = f"I couldn't create an image prompt right now. ({e})"
                return "text", fallback, None, {"role": "assistant", "type": "text", "content": fallback}

        # Unknown function
        fallback = "I'm not sure how to do that."
        return "text", fallback, None, {"role": "assistant", "type": "text", "content": fallback}

    # Model returned plain text
    text = (intent.get("text") or "").strip() or "I didn't quite get that. Can you rephrase?"
    return "text", text, None, {"role": "assistant", "type": "text", "content": text}
