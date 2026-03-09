# TutorX API Reference

Quick reference for TutorX API endpoints.

## Base URLs

- **TutorX Actions**: `/api/tutorx/`
- **User Instructions**: `/api/settings/`

## Authentication

All endpoints require authentication. Include token in header:
```
Authorization: Bearer <token>
```

## Lesson content (single JSON field)

TutorX lesson body is stored in `Lesson.tutorx_content` as a single BlockNote JSON string (same pattern as book page content). Per-block list/create/detail endpoints are no longer used.

### GET /api/tutorx/lessons/{lesson_id}/content/

Return the lesson's BlockNote content as a JSON string.

**Path Parameters**: `lesson_id` (UUID)

**Response** (200 OK):
```json
{
  "content": "[{\"id\":\"...\",\"type\":\"paragraph\",\"content\":[],\"props\":{}},...]"
}
```

Empty or new lessons may return `"content": ""`. Frontend treats empty string as empty document.

**Permission**: Course teacher or enrolled student.

---

### PUT /api/tutorx/lessons/{lesson_id}/content/

Save BlockNote JSON to `lesson.tutorx_content`. Used by the frontend for manual save with images in one request.

**Path Parameters**: `lesson_id` (UUID)

**Permission**: Course teacher only.

**Request**: `Content-Type: multipart/form-data`

| Part name | Type | Description |
|-----------|------|-------------|
| `content` | string (JSON) | Full BlockNote document (array of blocks). New image blocks must use `props.url` = `"__pending__<blockId>"` so the backend can match with file parts. |
| `deleted_image_urls` | string (JSON) | Array of GCS URLs to delete (images the user removed). |
| `image_<blockId>` | file | One file per new image; key = block id (e.g. `image_abc123`). |

**Backend processing**:
1. Upload each `image_<blockId>` file to GCS (folder `tutorx-images`), get URL.
2. Parse `content` JSON; in image blocks, replace each `__pending__<blockId>` in `props.url` with the corresponding uploaded URL.
3. Delete from GCS every URL in `deleted_image_urls`.
4. Save the final JSON string to `lesson.tutorx_content`.
5. Return `{ "content": "<saved JSON string>" }`.

**Response** (200 OK):
```json
{
  "content": "[{\"id\":\"...\",\"type\":\"paragraph\",...},...]"
}
```

---

### POST /api/tutorx/lessons/{lesson_id}/ask/

Student Ask AI: send a question about selected text in a TutorX lesson. The frontend sends sentence-level context (lesson title, optional context_before, current_sentence, selected_text, question, optional action_type) to control token usage. Used for the first message and for follow-up questions in the same conversation (each request is independent; no conversation history is sent).

**Path Parameters**: `lesson_id` (UUID)

**Request Body** (JSON):
```json
{
  "lesson_title": "string (required)",
  "context_before": "string (optional, up to 2 sentences before current)",
  "current_sentence": "string (required, full sentence containing selection)",
  "selected_text": "string (required)",
  "question": "string (required)",
  "action_type": "string (optional, e.g. explain_more, simplify, define, custom)"
}
```

**Response** (200 OK):
```json
{
  "answer": "Markdown-formatted explanation...",
  "model": "gemini-1.5-flash"
}
```

**Permission**: Course teacher or enrolled student. Lesson must exist and have `type == 'tutorx'`.

**Status Codes**:
- `200 OK`: Success
- `400 Bad Request`: Invalid request body
- `403 Forbidden`: User is not teacher or enrolled student
- `404 Not Found`: Lesson not found
- `500 Internal Server Error`: AI/service error

**Implementation**: `tutorx/views.py` → `TutorXLessonAskView`, `tutorx/serializers.py` → `StudentAskRequestSerializer` / `StudentAskResponseSerializer`, `tutorx/services/ai.py` → `TutorXAIService.ask_student()`. See `tutorx/STUDENT_ASK_AI.md`.

---

### POST /api/tutorx/lessons/{lesson_id}/chat/

Lesson chat: send a message and get an AI reply. The backend infers intent (explain, generate questions, draw explainer image, or plain text) and returns either plain text or structured data. Conversation is stateless: send the full conversation list with each request.

**Path Parameters**: `lesson_id` (UUID)

**Request Body** (JSON):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | Yes | The user's message. |
| `conversation` | array | No | Previous messages in this chat. Each item: `{ "role": "user" \| "assistant", "content"?: string, "type"?: "text" \| "qanda" \| "explainer_image", "data"?: object }`. Default: `[]`. |

**Response** (200 OK):

| Field | Type | Description |
|-------|------|-------------|
| `response_type` | string | `"text"` \| `"qanda"` \| `"explainer_image"`. Tells the client which template to use for the **latest** reply. |
| `content` | string | Present when `response_type === "text"`. The assistant's plain-text or markdown reply. |
| `data` | object | Present when `response_type === "qanda"` or `"explainer_image"`. See below. |
| `conversation` | array | Full conversation including the new user message and the new assistant message. Use for rendering history and for the next request. |

**When `response_type === "qanda"`**, `data` has:

- `questions`: array of `{ question_text, type, difficulty, content: { options?, correct_answer, ... }, explanation? }` (quiz-style).
- `message`: string (e.g. "Do you want harder questions?").

**When `response_type === "explainer_image"`**, `data` has:

- `image_description`: string (short description for accessibility).
- `image_prompt`: string (prompt for an image generation API).

**Permission**: Course teacher or enrolled student. Lesson must exist and have `type == 'tutorx'`.

**Status Codes**: `200 OK`, `400 Bad Request`, `403 Forbidden`, `404 Not Found`, `500 Internal Server Error`.

**Implementation**: `tutorx/views.py` → `LessonChatView`, `tutorx/services/lesson_chat.py` (intent + dispatch), `tutorx/services/handlers.py` (handlers). See `tutorx/docs/LESSON_CHAT_TUTORIAL.md` and `tutorx/docs/LESSON_CHAT_FRONTEND.md`.

---

### POST /api/tutorx/images/upload/

Upload a single image for TutorX (e.g. used by other clients). The **PUT /content/** multipart endpoint handles images in the main save flow.

**Request**: `multipart/form-data` with `image` (file).

**Response**:
```json
{
  "image_url": "https://storage.googleapis.com/...",
  "file_size": 1024000,
  "file_size_mb": 1.0,
  "file_extension": "jpg",
  "original_filename": "name.jpg",
  "message": "Image uploaded successfully"
}
```

**Permission**: Teacher. Images are stored in GCS under `tutorx-images/`.

---

### DELETE /api/tutorx/images/delete/

Delete an image from GCS by URL (e.g. used by other clients). The **PUT /content/** multipart endpoint handles deletes in the main save flow.

**Request Body**:
```json
{
  "image_url": "https://storage.googleapis.com/..."
}
```

**Response**: `{ "message": "Successfully deleted ..." }`

**Permission**: Teacher.

---

## Block Actions

### POST /api/tutorx/blocks/{action_type}/

Perform an AI action on a content block.

**Path Parameters**:
- `action_type` (required): One of `explain_more`, `give_examples`, `simplify`, `summarize`, `generate_questions`

**Request Body**:
```json
{
    "block_content": "string (required)",
    "block_type": "text|code|image|diagram (default: text)",
    "context": {
        "lesson_title": "string",
        "target_audience": "string"
    },
    "user_prompt": "string (optional)",
    "user_prompt_changed": false,
    "temperature": 0.7,
    "max_tokens": null
}
```

**Action-Specific Parameters**:

**explain_more**: No additional parameters

**give_examples**:
```json
{
    "num_examples": 3,
    "example_type": "practical|real-world|simple|advanced"
}
```

**simplify**:
```json
{
    "target_level": "beginner|intermediate|advanced"
}
```

**summarize**:
```json
{
    "length": "brief|medium|detailed"
}
```

**generate_questions**:
```json
{
    "num_questions": 3,
    "question_types": ["multiple_choice", "short_answer"]
}
```

**Response** (varies by action):

**explain_more**:
```json
{
    "explanation": "string",
    "model": "string"
}
```

**give_examples**:
```json
{
    "examples": ["string"],
    "raw_response": "string",
    "model": "string"
}
```

**simplify**:
```json
{
    "simplified_content": "string",
    "model": "string"
}
```

**summarize**:
```json
{
    "summary": "string",
    "model": "string"
}
```

**generate_questions**:
```json
{
    "questions": [
        {
            "question": "string",
            "type": "string",
            "difficulty": "string"
        }
    ],
    "model": "string"
}
```

**Status Codes**:
- `200 OK`: Success
- `400 Bad Request`: Invalid request or validation error
- `401 Unauthorized`: Authentication required
- `500 Internal Server Error`: Server error

## User Instruction Management

### GET /api/settings/tutorx-instructions/{action_type}/

Get user instruction for a specific action type.

**Path Parameters**:
- `action_type` (required): One of `explain_more`, `give_examples`, `simplify`, `summarize`, `generate_questions`

**Behavior**:
- If `UserTutorXInstruction` exists: Returns it
- If `UserTutorXInstruction` doesn't exist (null):
  1. Fetches default from `TutorXUserInstructionsDefaults`
  2. Creates new `UserTutorXInstruction` with that default
  3. Saves to database
  4. Returns the newly created instruction

**Note**: This endpoint always returns a populated instruction. It never returns null/empty.

**Response**:
```json
{
    "id": "uuid",
    "action_type": "explain_more",
    "user_instruction": "string",
    "is_customized": true,
    "created_at": "ISO 8601 datetime",
    "updated_at": "ISO 8601 datetime"
}
```

**Status Codes**:
- `200 OK`: Success
- `400 Bad Request`: Invalid action type
- `401 Unauthorized`: Authentication required
- `500 Internal Server Error`: Server error

### PUT /api/settings/tutorx-instructions/{action_type}/

Update user instruction for a specific action type.

**Path Parameters**:
- `action_type` (required): One of `explain_more`, `give_examples`, `simplify`, `summarize`, `generate_questions`

**Request Body**:
```json
{
    "user_instruction": "string (required, max 5000 chars)"
}
```

**Response**: Same as GET

**Status Codes**:
- `200 OK`: Success
- `400 Bad Request`: Validation error or invalid action type
- `401 Unauthorized`: Authentication required
- `500 Internal Server Error`: Server error

### POST /api/settings/tutorx-instructions/{action_type}/

Reset user instruction to default.

**Path Parameters**:
- `action_type` (required): One of `explain_more`, `give_examples`, `simplify`, `summarize`, `generate_questions`

**Response**:
```json
{
    "id": "uuid",
    "action_type": "explain_more",
    "user_instruction": "string (default)",
    "is_customized": false,
    "message": "Instruction reset to default",
    "created_at": "ISO 8601 datetime",
    "updated_at": "ISO 8601 datetime"
}
```

**Status Codes**:
- `200 OK`: Success
- `400 Bad Request`: Invalid action type
- `401 Unauthorized`: Authentication required
- `500 Internal Server Error`: Server error

## Error Responses

All endpoints return errors in this format:

```json
{
    "error": "Error message",
    "details": "Detailed error information (optional)"
}
```

## Example Requests

### Get User Instruction

```bash
curl -X GET \
  http://localhost:8000/api/settings/tutorx-instructions/explain_more/ \
  -H "Authorization: Bearer <token>"
```

### Update User Instruction

```bash
curl -X PUT \
  http://localhost:8000/api/settings/tutorx-instructions/explain_more/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "user_instruction": "Please explain {block_content} using simple language..."
  }'
```

### Perform Explain More Action

```bash
curl -X POST \
  http://localhost:8000/api/tutorx/blocks/explain_more/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "block_content": "Python is a programming language",
    "block_type": "text",
    "user_prompt": "Please explain {block_content} using simple language",
    "user_prompt_changed": false,
    "context": {
      "target_audience": "ages 8-12"
    }
  }'
```

### Generate Examples

```bash
curl -X POST \
  http://localhost:8000/api/tutorx/blocks/give_examples/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "block_content": "Variables store data",
    "block_type": "text",
    "num_examples": 3,
    "example_type": "practical"
  }'
```

## JavaScript Examples

### Load User Instructions

```javascript
async function loadUserInstructions() {
    const actionTypes = ['explain_more', 'give_examples', 'simplify', 'summarize', 'generate_questions'];
    const instructions = {};
    
    for (const actionType of actionTypes) {
        const response = await fetch(
            `/api/settings/tutorx-instructions/${actionType}/`,
            {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            }
        );
        instructions[actionType] = await response.json();
    }
    
    return instructions;
}
```

### Perform Action

```javascript
async function explainMore(blockContent, userPrompt, userPromptChanged) {
    const response = await fetch('/api/tutorx/blocks/explain_more/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            block_content: blockContent,
            block_type: 'text',
            user_prompt: userPrompt,
            user_prompt_changed: userPromptChanged
        })
    });
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to perform action');
    }
    
    return await response.json();
}
```

### Update Instruction

```javascript
async function updateInstruction(actionType, instruction) {
    const response = await fetch(
        `/api/settings/tutorx-instructions/${actionType}/`,
        {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                user_instruction: instruction
            })
        }
    );
    
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to update instruction');
    }
    
    return await response.json();
}
```

