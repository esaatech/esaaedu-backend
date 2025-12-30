# TutorX - AI-Powered Block Actions

## Overview

TutorX is a Django app that provides AI-powered actions on content blocks within lessons. It enables students and teachers to interact with lesson content through actions like "explain more", "give examples", "simplify", "summarize", and "generate questions".

## Architecture

### Three-Layer Prompt System

TutorX uses a sophisticated three-layer prompt system that separates concerns:

1. **System Instruction** (Admin-managed, global)
2. **Default User Instruction** (Admin-managed, template for new users)
3. **User Instruction** (User-customizable, per-user settings)

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1: System Instruction (Global)                    │
│ - Model: TutorXBlockActionConfig.system_instruction     │
│ - Managed by: Admins only                               │
│ - Purpose: Base AI behavior and role definition         │
│ - Same for: Everyone                                     │
└─────────────────────────────────────────────────────────┘
                          +
┌─────────────────────────────────────────────────────────┐
│ Layer 2: Default User Instruction (Template)            │
│ - Model: TutorXUserInstructionsDefaults                 │
│ - Managed by: Admins                                    │
│ - Purpose: Starting point for new users                 │
│ - Used when: User hasn't customized yet                 │
└─────────────────────────────────────────────────────────┘
                          +
┌─────────────────────────────────────────────────────────┐
│ Layer 3: User Instruction (Customizable)                 │
│ - Model: UserTutorXInstruction (in settings app)       │
│ - Managed by: Each user                                  │
│ - Purpose: User's personalized instructions             │
│ - One per: User per action type                          │
└─────────────────────────────────────────────────────────┘
```

## Dependencies

### External App Dependency: Lesson Model

**Important**: The `TutorXBlock` model has a ForeignKey dependency on `courses.Lesson` from the `courses` app.

```python
# In tutorx/models.py
lesson = models.ForeignKey(
    'courses.Lesson',
    on_delete=models.CASCADE,
    related_name='tutorx_blocks',
)
```

**What this means**:
- TutorX blocks are linked to lessons from the `courses` app
- If you're moving TutorX to another project, you need to:
  1. Either have a `Lesson` model in your project (in any app)
  2. Or modify the ForeignKey to point to your equivalent model (e.g., `Content`, `Chapter`, `Module`, etc.)

**For this project**: The `Lesson` model is in the `courses` app, so the relationship is:
- `courses.Lesson` → Many `tutorx.TutorXBlock` instances
- Access blocks via: `lesson.tutorx_blocks.all()`

**For other projects**: To adapt TutorX:
1. Identify your equivalent model (what contains the content that blocks belong to)
2. Update the ForeignKey in `TutorXBlock`:
   ```python
   # Example: If your model is called 'Content' in 'content' app
   content = models.ForeignKey(
       'content.Content',
       on_delete=models.CASCADE,
       related_name='tutorx_blocks',
   )
   ```
3. Update all references from `lesson` to your model name
4. Update the `__str__` method and any methods that reference `self.lesson`

**Note**: The relationship is **one-to-many** (one lesson/content → many blocks). This is intentional for simplicity and performance. See the model design section for details.

## Models

### 1. TutorXBlockActionConfig (tutorx app)

**Location**: `tutorx/models.py`

**Purpose**: Stores system instructions for each action type. These are admin-managed base prompts that define the AI's role and behavior.

**Fields**:
- `action_type`: One of `explain_more`, `give_examples`, `simplify`, `summarize`, `generate_questions`
- `display_name`: Human-readable name
- `description`: Description of the action
- `system_instruction`: Base system prompt (admin-only, cannot be changed by users)
- `version`: Auto-incremented when system_instruction changes
- `is_active`: Whether this config is active
- Audit fields: `created_at`, `updated_at`, `created_by`, `last_modified_by`

**Admin**: Registered in `tutorx/admin.py`

**Example**:
```python
{
    "action_type": "explain_more",
    "display_name": "Explain More",
    "system_instruction": "You are an expert educational assistant...",
    "version": 1,
    "is_active": True
}
```

### 2. TutorXUserInstructionsDefaults (tutorx app)

**Location**: `tutorx/models.py`

**Purpose**: Stores default user instruction templates. These are shown to users initially and can be customized.

**Fields**:
- `action_type`: One of the action types
- `display_name`: Human-readable name
- `description`: Description
- `default_user_instruction`: Default instruction template (admin-managed)
- `version`: Auto-incremented when default_user_instruction changes
- `is_active`: Whether this default is active
- Audit fields: `created_at`, `updated_at`, `created_by`, `last_modified_by`

**Admin**: Registered in `tutorx/admin.py`

**Example**:
```python
{
    "action_type": "explain_more",
    "default_user_instruction": "Please explain {block_content} using simple language...",
    "version": 1,
    "is_active": True
}
```

### 3. TutorXBlock (tutorx app)

**Location**: `tutorx/models.py`

**Purpose**: Stores individual content blocks within a TutorX lesson. Each block can be of type text, code, image, or diagram.

**Dependency**: Requires a `Lesson` model (or equivalent) from another app. In this project, it's `courses.Lesson`.

**Fields**:
- `lesson`: ForeignKey to `courses.Lesson` (links block to a lesson)
- `block_type`: ChoiceField (text, code, image, diagram)
- `content`: TextField (the actual block content)
- `order`: IntegerField (sequence within the lesson, 1, 2, 3, ...)
- `metadata`: JSONField (block-specific data like code language, image URL, caption, etc.)
- `created_at`, `updated_at`: Timestamps

**Unique Constraint**: `(lesson, order)` ensures no duplicate orders per lesson

**Methods**:
- `get_content_for_ai()`: Formats content for AI processing based on block type

**Admin**: Registered in `tutorx/admin.py`

**Example**:
```python
{
    "id": "uuid",
    "lesson": <Lesson>,
    "block_type": "code",
    "content": "def hello():\n    print('Hello')",
    "order": 1,
    "metadata": {"language": "python"},
    "created_at": "...",
    "updated_at": "..."
}
```

**Relationship**:
- One `Lesson` → Many `TutorXBlock` instances (one-to-many)
- Access blocks: `lesson.tutorx_blocks.all()`
- Blocks are ordered by `order` field

**For other projects**: If you don't have a `Lesson` model, you'll need to:
1. Create a model that represents the container for blocks (e.g., `Content`, `Chapter`, `Module`)
2. Update the ForeignKey in `TutorXBlock` to point to your model
3. Update all code that references `lesson` to use your model name

### 4. UserTutorXInstruction (settings app)

**Location**: `settings/models.py`

**Purpose**: Stores user-specific instructions. Each user can customize their instructions per action type.

**Fields**:
- `user`: ForeignKey to User
- `action_type`: One of the action types
- `user_instruction`: User's custom instruction text
- `created_at`, `updated_at`: Timestamps

**Unique Constraint**: One instruction per user per action type

**Methods**:
- `get_or_create_settings(user, action_type)`: Gets or creates instruction, loading default if doesn't exist
- `reset_to_default()`: Resets instruction to default from `TutorXUserInstructionsDefaults`
- `is_customized()`: Checks if instruction differs from default

**Admin**: Registered in `settings/admin.py`

**Example**:
```python
{
    "user": <User>,
    "action_type": "explain_more",
    "user_instruction": "Please explain {block_content} using simple language for ages 8-12..."
}
```

## API Endpoints

### Block Actions

**Endpoint**: `POST /api/tutorx/blocks/<action_type>/`

**Authentication**: Required

**Action Types**:
- `explain_more`: Expand on block content with more detail
- `give_examples`: Generate examples related to block content
- `simplify`: Make content easier to understand
- `summarize`: Create a concise summary
- `generate_questions`: Create questions based on block content

**Request Body**:
```json
{
    "block_content": "Python is a programming language",
    "block_type": "text",
    "context": {
        "lesson_title": "Introduction to Python",
        "target_audience": "ages 8-12"
    },
    "user_prompt": "Please explain {block_content} using simple language...",
    "user_prompt_changed": false,
    "temperature": 0.7,
    "max_tokens": null,
    "num_examples": 3,  // For give_examples
    "example_type": "practical",  // For give_examples
    "target_level": "beginner",  // For simplify
    "length": "brief",  // For summarize
    "num_questions": 3,  // For generate_questions
    "question_types": ["multiple_choice", "short_answer"]  // For generate_questions
}
```

**Response** (varies by action type):

**explain_more**:
```json
{
    "explanation": "Python is a programming language that...",
    "model": "gemini-1.5-pro"
}
```

**give_examples**:
```json
{
    "examples": ["Example 1", "Example 2", "Example 3"],
    "raw_response": "...",
    "model": "gemini-1.5-pro"
}
```

**simplify**:
```json
{
    "simplified_content": "Python is like giving instructions to a computer...",
    "model": "gemini-1.5-pro"
}
```

**summarize**:
```json
{
    "summary": "Python is a programming language used for...",
    "model": "gemini-1.5-pro"
}
```

**generate_questions**:
```json
{
    "questions": [
        {
            "question": "What is Python?",
            "type": "multiple_choice",
            "difficulty": "easy"
        }
    ],
    "model": "gemini-1.5-pro"
}
```

**View**: `tutorx/views.py` → `BlockActionView`

**Serializer**: `tutorx/serializers.py` → `BlockActionRequestSerializer` (request), action-specific response serializers

### User Instruction Management

**Endpoint**: `GET /api/settings/tutorx-instructions/<action_type>/`

**Authentication**: Required

**Description**: Get user instruction for a specific action type.

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
    "user_instruction": "Please explain {block_content}...",
    "is_customized": true,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
}
```

**View**: `settings/views.py` → `UserTutorXInstructionView.get()`

**Serializer**: `settings/serializers.py` → `UserTutorXInstructionSerializer`

---

**Endpoint**: `PUT /api/settings/tutorx-instructions/<action_type>/`

**Authentication**: Required

**Description**: Update user instruction for a specific action type.

**Request Body**:
```json
{
    "user_instruction": "Please explain {block_content} using simple language for ages 8-12..."
}
```

**Response**: Same as GET

**View**: `settings/views.py` → `UserTutorXInstructionView.put()`

---

**Endpoint**: `POST /api/settings/tutorx-instructions/<action_type>/`

**Authentication**: Required

**Description**: Reset user instruction to default.

**Response**:
```json
{
    "id": "uuid",
    "action_type": "explain_more",
    "user_instruction": "Default instruction...",
    "is_customized": false,
    "message": "Instruction reset to default"
}
```

**View**: `settings/views.py` → `UserTutorXInstructionView.post()`

## Flow

### 1. Page Load (Frontend)

When the TutorX page mounts:

```javascript
// Load user instruction for each action type
GET /api/settings/tutorx-instructions/explain_more/
GET /api/settings/tutorx-instructions/give_examples/
// ... etc
```

**Backend Flow** (for each GET request):
1. Check if `UserTutorXInstruction` exists for this user + action_type
2. **If exists**: Return the user's instruction (customized or default)
3. **If doesn't exist (null)**:
   - Fetch default from `TutorXUserInstructionsDefaults` (admin-managed)
   - Create new `UserTutorXInstruction` with that default
   - Save to database
   - Return the newly created instruction

**Response**: Always returns a `UserTutorXInstruction` object:
- If user has customized: Returns their custom instruction
- If user hasn't customized: Returns instruction with default from `TutorXUserInstructionsDefaults`
- If record didn't exist: Creates it with default and returns it

**Frontend displays**: The instruction in an editable field (always populated, never empty)

### 2. User Edits Instruction (Optional)

User can:
- View their current instruction
- Edit the instruction
- Check a box to indicate they want to save it (`user_prompt_changed = true`)

### 3. User Performs Action

When user clicks "Explain More" (or any action):

```javascript
POST /api/tutorx/blocks/explain_more/
{
    "block_content": "...",
    "block_type": "text",
    "user_prompt": "User's instruction text...",
    "user_prompt_changed": true,  // If user edited
    // ... other params
}
```

**Backend Flow**:
1. Validates request using `BlockActionRequestSerializer`
2. If `user_prompt` not provided: Loads from `UserTutorXInstruction` (or uses default)
3. If `user_prompt_changed = true`: Saves to `UserTutorXInstruction`
4. Loads `system_instruction` from `TutorXBlockActionConfig`
5. Calls `TutorXAIService.explain_more()` with:
   - `system_instruction` (from DB)
   - `user_prompt` (from request or DB)
   - `block_content`, `context`, etc.
6. Returns AI response

### 4. AI Service Processing

`TutorXAIService`:
- Receives `user_prompt` as parameter (no DB access)
- Loads `system_instruction` from `TutorXBlockActionConfig`
- Builds combined prompt
- Calls Gemini API
- Returns structured response

## Services

### TutorXAIService

**Location**: `tutorx/services/ai.py`

**Purpose**: AI service for TutorX block actions. Extends `GeminiService` to provide block-specific functionality.

**Key Methods**:
- `explain_more(block_content, block_type, context, user_prompt, ...)`
- `give_examples(block_content, block_type, context, user_prompt, num_examples, ...)`
- `simplify(block_content, block_type, context, user_prompt, target_level, ...)`
- `summarize(block_content, block_type, context, user_prompt, length, ...)`
- `generate_questions(block_content, block_type, context, user_prompt, num_questions, ...)`

**Design Principle**: Service only receives `user_prompt` as parameter. It does NOT access `UserTutorXInstruction` directly. Views handle data persistence.

**Internal Methods**:
- `_get_system_instruction(action_type)`: Loads from `TutorXBlockActionConfig`
- `_get_default_user_prompt(action_type)`: Loads from `TutorXUserInstructionsDefaults`
- `_build_prompt(...)`: Combines system instruction, user prompt, block content, and context

## Serializers

### Request Serializers

**Location**: `tutorx/serializers.py`

- `BlockActionRequestSerializer`: Validates all block action requests
  - Validates `block_content` (required, not empty)
  - Validates `block_type` (choices: text, code, image, diagram)
  - Validates `temperature` (0.0-1.0)
  - Validates action-specific parameters

### Response Serializers

**Location**: `tutorx/serializers.py`

- `ExplainMoreResponseSerializer`: `{explanation, model}`
- `GiveExamplesResponseSerializer`: `{examples, raw_response?, model}`
- `SimplifyResponseSerializer`: `{simplified_content, model}`
- `SummarizeResponseSerializer`: `{summary, model}`
- `GenerateQuestionsResponseSerializer`: `{questions, model}`

### Settings Serializers

**Location**: `settings/serializers.py`

- `UserTutorXInstructionSerializer`: Serializes `UserTutorXInstruction` model
  - Fields: `id`, `action_type`, `user_instruction`, `is_customized`, `created_at`, `updated_at`
  - Validates `user_instruction` (not empty, max 5000 chars)

## Management Commands

### init_tutorx_prompts

**Location**: `tutorx/management/commands/init_tutorx_prompts.py`

**Usage**: `python manage.py init_tutorx_prompts`

**Purpose**: Initialize default `TutorXBlockActionConfig` and `TutorXUserInstructionsDefaults` entries for all action types.

**Features**:
- Idempotent (safe to run multiple times)
- Auto-increments version when content changes
- Populates both system instructions and default user instructions
- Creates entries for: `explain_more`, `give_examples`, `simplify`, `summarize`, `generate_questions`

**Run after**: Creating the app or when adding new action types

## Admin Interface

### TutorXBlockActionConfig

**Location**: `tutorx/admin.py`

**Access**: Django Admin → TutorX → TutorX Block Action Configs

**Features**:
- Admin-only editing
- Version tracking
- Audit trail (created_by, last_modified_by)

### TutorXUserInstructionsDefaults

**Location**: `tutorx/admin.py`

**Access**: Django Admin → TutorX → TutorX User Instructions Defaults

**Features**:
- Admin-only editing
- Version tracking
- Audit trail

### UserTutorXInstruction

**Location**: `settings/admin.py`

**Access**: Django Admin → Settings → User TutorX Instructions

**Features**:
- View all user instructions
- Search by user email/name
- Filter by action type
- See customization status

## Frontend Integration Guide

### 1. Load User Instructions on Page Mount

```javascript
// Load instructions for all action types
const actionTypes = ['explain_more', 'give_examples', 'simplify', 'summarize', 'generate_questions'];

const instructions = {};
for (const actionType of actionTypes) {
    const response = await fetch(`/api/settings/tutorx-instructions/${actionType}/`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    instructions[actionType] = await response.json();
}
```

### 2. Display Instruction in UI

```javascript
// Show instruction in editable field
<textarea
    value={instructions.explain_more.user_instruction}
    onChange={(e) => setUserInstruction(e.target.value)}
/>
<label>
    <input
        type="checkbox"
        checked={userPromptChanged}
        onChange={(e) => setUserPromptChanged(e.target.checked)}
    />
    Save this instruction
</label>
```

### 3. Perform Action

```javascript
const performAction = async (actionType, blockContent) => {
    const response = await fetch(`/api/tutorx/blocks/${actionType}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            block_content: blockContent,
            block_type: 'text',
            user_prompt: userInstruction,
            user_prompt_changed: userPromptChanged,
            // ... other params
        })
    });
    
    const result = await response.json();
    // Display result.explanation, result.examples, etc.
};
```

### 4. Update Instruction

```javascript
const updateInstruction = async (actionType, instruction) => {
    await fetch(`/api/settings/tutorx-instructions/${actionType}/`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            user_instruction: instruction
        })
    });
};
```

### 5. Reset to Default

```javascript
const resetInstruction = async (actionType) => {
    const response = await fetch(`/api/settings/tutorx-instructions/${actionType}/`, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
    const updated = await response.json();
    // Update UI with updated.user_instruction
};
```

## Benefits

1. **Separation of Concerns**: System instructions (admin), defaults (admin), user instructions (user)
2. **Flexibility**: Users can customize instructions to their needs
3. **Consistency**: Base system instructions ensure consistent AI behavior
4. **Version Control**: System instructions and defaults are versioned
5. **Admin Control**: Admins can update prompts without code changes
6. **User Personalization**: Users can tailor AI responses to their teaching/learning style
7. **Clean Architecture**: Service layer focused on AI, views handle data persistence

## Testing

### Test AI Service

```python
from tutorx.services.ai import TutorXAIService

service = TutorXAIService()
result = service.explain_more(
    block_content="Python is a programming language",
    block_type="text",
    user_prompt="Please explain {block_content} using simple language"
)
print(result['explanation'])
```

### Test API Endpoints

```bash
# Get user instruction
curl -X GET http://localhost:8000/api/settings/tutorx-instructions/explain_more/ \
  -H "Authorization: Bearer <token>"

# Update user instruction
curl -X PUT http://localhost:8000/api/settings/tutorx-instructions/explain_more/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"user_instruction": "Custom instruction..."}'

# Perform action
curl -X POST http://localhost:8000/api/tutorx/blocks/explain_more/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "block_content": "Python is a programming language",
    "block_type": "text",
    "user_prompt": "Please explain {block_content}",
    "user_prompt_changed": false
  }'
```

## Migration Path

1. **Initial Setup**: Run `python manage.py init_tutorx_prompts` to create default configs
2. **Admin Configuration**: Admins customize system instructions and defaults in Django Admin
3. **User Adoption**: Users gradually customize their instructions as needed
4. **Updates**: Admins can update system instructions and defaults without affecting user customizations

## File Structure

```
tutorx/
├── models.py                    # TutorXBlockActionConfig, TutorXUserInstructionsDefaults, TutorXBlock
├── admin.py                     # Admin interfaces
├── views.py                     # BlockActionView
├── serializers.py               # Request/response serializers
├── urls.py                      # URL configuration
├── services/
│   └── ai.py                    # TutorXAIService
├── management/
│   └── commands/
│       └── init_tutorx_prompts.py
└── README.md                    # This file

settings/
├── models.py                    # UserTutorXInstruction
├── admin.py                     # UserTutorXInstruction admin
├── views.py                     # UserTutorXInstructionView
├── serializers.py               # UserTutorXInstructionSerializer
└── urls.py                      # Settings URLs

courses/                          # External dependency
└── models.py                    # Lesson model (required for TutorXBlock)
```

## Porting to Another Project

If you're moving TutorX to another Django project, here's what you need to adapt:

### 1. Lesson Model Dependency

**Current**: `TutorXBlock` has a ForeignKey to `courses.Lesson`

**To adapt**:
1. Identify your equivalent model (what contains content that blocks belong to)
2. Update the ForeignKey in `tutorx/models.py`:
   ```python
   # Change from:
   lesson = models.ForeignKey('courses.Lesson', ...)
   
   # To your model, e.g.:
   content = models.ForeignKey('content.Content', ...)
   # or
   chapter = models.ForeignKey('chapters.Chapter', ...)
   # or
   module = models.ForeignKey('modules.Module', ...)
   ```
3. Update all references:
   - `self.lesson` → `self.content` (or your model name)
   - `lesson.tutorx_blocks` → `content.tutorx_blocks`
   - Update `__str__` method
   - Update admin interface
   - Update any views/serializers that reference `lesson`

### 2. Settings App Dependency

**Current**: `UserTutorXInstruction` is in the `settings` app

**To adapt**:
- Option A: Keep it in your settings app (if you have one)
- Option B: Move it to the `tutorx` app
- Option C: Create a new app for user settings

### 3. Required Models

**Must have**:
- A model that represents the container for blocks (Lesson, Content, Chapter, etc.)
- This model should have a title/name field for display

**Nice to have**:
- Course/container relationship (e.g., Course → Lessons → Blocks)
- Ordering field on your container model

### 4. Migration Steps

1. Copy `tutorx` app to your project
2. Update ForeignKey in `TutorXBlock` model
3. Update all code references from `lesson` to your model name
4. Run migrations: `python manage.py makemigrations tutorx`
5. Apply migrations: `python manage.py migrate tutorx`
6. Run initialization: `python manage.py init_tutorx_prompts`

### 5. Example: Adapting for a Blog Project

If you have a `Post` model instead of `Lesson`:

```python
# In tutorx/models.py
class TutorXBlock(models.Model):
    # Change from:
    # lesson = models.ForeignKey('courses.Lesson', ...)
    
    # To:
    post = models.ForeignKey(
        'blog.Post',
        on_delete=models.CASCADE,
        related_name='tutorx_blocks',
        help_text="Post this block belongs to"
    )
    
    # Update __str__:
    def __str__(self):
        return f"{self.post.title} - Block {self.order} ({self.get_block_type_display()})"
```

Then access blocks via: `post.tutorx_blocks.all()`

## Related Documentation

- `tutorx/PROMPT_ARCHITECTURE.md`: Detailed prompt architecture (may be outdated)
- `tutorx/DESIGN_CLARIFICATION.md`: Design decisions and clarifications (may be outdated)

