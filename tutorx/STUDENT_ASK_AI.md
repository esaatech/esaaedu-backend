# Student Ask AI (TutorX Lesson Ask)

## Overview

Students viewing a TutorX lesson can select text and ask the AI a question (e.g. "Explain more", "Simplify", or a custom question). The frontend sends **sentence-level context** (lesson title, optional context before, current sentence, selected text, question) to limit token usage. This backend endpoint answers each request independently; the frontend manages the conversation UI and follow-ups by reusing the same context with a new question.

## Endpoint

**POST** `/api/tutorx/lessons/<lesson_id>/ask/`

- **Path**: `lesson_id` (UUID).
- **Permission**: Authenticated user must be the **course teacher** or an **enrolled student** (e.g. via `EnrolledCourse`). Lesson must exist and have `type == 'tutorx'`.

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

**Errors**: 400 (validation), 403 (forbidden), 404 (lesson not found), 500 (AI error).

## Implementation

| Layer | File | Description |
|-------|------|-------------|
| **View** | `tutorx/views.py` | `TutorXLessonAskView` — POST only; resolves lesson by `lesson_id`; checks `lesson.type == 'tutorx'`; enforces teacher or enrolled student; validates body with `StudentAskRequestSerializer`; calls `TutorXAIService.ask_student()`; returns 200 with `StudentAskResponseSerializer` or 400/403/404/500. |
| **Serializers** | `tutorx/serializers.py` | `StudentAskRequestSerializer` — validates `lesson_title`, `context_before`, `current_sentence`, `selected_text`, `question`, `action_type`. `StudentAskResponseSerializer` — `answer`, `model`. |
| **Service** | `tutorx/services/ai.py` | `TutorXAIService.ask_student(lesson_title, current_sentence, selected_text, question, context_before=None, action_type=None, ...)` — builds a single prompt from the fields (no `block_content`); uses `_get_system_instruction(action_type)` for known action types or a generic tutor instruction for `custom`; calls `gemini_service.generate()`; returns `{'answer': raw, 'model': ...}`. |
| **URL** | `tutorx/urls.py` | `path('lessons/<uuid:lesson_id>/ask/', views.TutorXLessonAskView.as_view(), name='tutorx-lesson-ask')`. |

## Frontend

The React app (little-learners-tech repo) builds the payload in `src/utils/tutorxSentenceContext.ts` and calls `askTutorXAI(lessonId, payload)` from `src/services/api.ts`. See the frontend docs: `docs/tutorx-student-ask-ai.md`.

## API reference

See `tutorx/API_REFERENCE.md` for the full request/response and status codes.
