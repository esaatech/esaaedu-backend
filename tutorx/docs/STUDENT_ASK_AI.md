# Student Ask AI (TutorX Lesson Ask)

## Overview

Students viewing a TutorX lesson can select text and ask the AI a question (e.g. "Explain more", "Simplify", or a custom question). The frontend sends **sentence-level context** (lesson title, optional context before, current sentence, selected text, question) to limit token usage. This backend endpoint answers each request independently; the frontend manages the conversation UI and follow-ups by reusing the same context with a new question.

Ask AI is **disabled by default**. Teachers enable it per lesson via `Lesson.show_ask_ai` (checkbox **Show Ask AI** in Course Management). Existing lessons remain off until a teacher checks the box and saves.

## Lesson flag: `show_ask_ai`

| Field | Model | Default | Meaning |
|-------|--------|---------|---------|
| `show_ask_ai` | `courses.Lesson` | `False` | When `True`, students may use Ask AI UI and call ask/chat APIs for this TutorX lesson. |

- Exposed on teacher create/update and list serializers, and on student lesson list/detail (so `CourseViewer` can gate the UI).
- Migration: `courses/migrations/0069_lesson_show_ask_ai.py`.
- **API enforcement**: In `TutorXLessonAskView` and `LessonChatView`, if the requester is a **student** and `lesson.show_ask_ai` is `False`, the request is rejected (so the UI flag cannot be bypassed). Course teachers are not blocked by this flag.

## Endpoint

**POST** `/api/tutorx/lessons/<lesson_id>/ask/`

- **Path**: `lesson_id` (UUID).
- **Permission**: Authenticated user must be the **course teacher** or an **enrolled student** (e.g. via `EnrolledCourse`). Lesson must exist and have `type == 'tutorx'`. Enrolled students additionally require `show_ask_ai == True`.

## Request

**Content-Type**: `application/json`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `lesson_title` | string | Yes | Title of the lesson. |
| `context_before` | string | No | Up to 2 sentences before the current sentence. |
| `current_sentence` | string | Yes | Full sentence containing the selection. |
| `selected_text` | string | Yes | Exact text selected by the user. |
| `question` | string | Yes | User's question (from quick action or custom input). |
| `action_type` | string | No | One of: `explain_more`, `give_examples`, `simplify`, `summarize`, `generate_questions`, `custom`. |

## Response

**200 OK**:

```json
{
  "answer": "Markdown-formatted explanation...",
  "model": "gemini-1.5-flash"
}
```

**Errors**: 400 (validation), 403 (forbidden / Ask AI disabled for students), 404 (lesson not found), 500 (AI error).

## Implementation

| Layer | File | Description |
|-------|------|-------------|
| **Model** | `courses/models.py` | `Lesson.show_ask_ai` BooleanField, default `False`. |
| **View** | `tutorx/views.py` | `TutorXLessonAskView` — POST only; resolves lesson; checks `type == 'tutorx'`; enforces teacher or enrolled student; **rejects students when `not lesson.show_ask_ai`**; validates body; calls `TutorXAIService.ask_student()`. |
| **Serializers** | `tutorx/serializers.py` / `courses/serializers.py` | Ask request/response serializers; lesson list/detail/create-update include `show_ask_ai`. |
| **Service** | `tutorx/services/ai.py` | `TutorXAIService.ask_student(...)`. |
| **URL** | `tutorx/urls.py` | `path('lessons/<uuid:lesson_id>/ask/', ...)`. |

The same `show_ask_ai` student gate applies to **POST** `/api/tutorx/lessons/<lesson_id>/chat/` (`LessonChatView`).

## Frontend

The React app (little-learners-tech repo) gates UI on `show_ask_ai === true`, builds the ask payload in `src/apps/tutorx/utils/tutorxSentenceContext.ts`, and calls `askTutorXAI(lessonId, payload)`. See the frontend docs: `docs/tutorx-student-ask-ai.md`.

## API reference

See `tutorx/docs/API_REFERENCE.md` for the full request/response and status codes.
