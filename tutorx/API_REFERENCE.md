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

