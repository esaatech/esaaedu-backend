# TutorX Prompt Architecture

## Overview

TutorX uses a **three-layer prompt system** that separates admin-managed base prompts from user-customizable prompts. This ensures consistency while allowing personalization.

## Architecture

### Layer 1: System Instruction (Admin-Only, Global)

**Model**: `TutorXBlockActionConfig.system_instruction`

- **Managed by**: Admins only (via Django Admin)
- **Purpose**: Base system instruction that defines the AI's role and behavior
- **Cannot be changed by**: Users
- **Versioned**: Auto-increments when updated
- **Stored in**: `tutorx` app, database table `tutorx_tutorxblockactionconfig`
- **Same for**: Everyone

**Example System Instruction** (for "explain_more"):
```
You are an expert educational assistant helping students understand content better.
Your role is to provide clear, detailed explanations that help learners grasp concepts more deeply.
Always maintain an educational, supportive tone.
```

### Layer 2: Default User Instruction (Admin-Managed Template)

**Model**: `TutorXUserInstructionsDefaults.default_user_instruction`

- **Managed by**: Admins (via Django Admin)
- **Purpose**: Default instruction template shown to new users
- **Used when**: User hasn't customized their instruction yet
- **Versioned**: Auto-increments when updated
- **Stored in**: `tutorx` app, database table `tutorx_tutorxuserinstructionsdefaults`

**Example Default User Instruction** (for "explain_more"):
```
Please explain {block_content} in a way that:
- Uses simple language suitable for {target_audience}
- Includes real-world examples
- Breaks down complex concepts step-by-step
```

### Layer 3: User Instruction (User-Customizable)

**Model**: `UserTutorXInstruction.user_instruction`

- **Managed by**: Users (via frontend API)
- **Purpose**: User's custom instructions/preferences
- **Can be changed by**: Users (through frontend)
- **Stored in**: `settings` app, database table `settings_usertutorxinstruction`
- **One per**: User per action type

**Example User Instruction** (for "explain_more"):
```
Please explain {block_content} using simple language for ages 8-12.
Include real-world examples and use step-by-step breakdowns.
```

## How It Works

### 1. Admin Setup (One-Time)

Admin creates entries in Django Admin:

**TutorXBlockActionConfig** (for each action type):
- `explain_more`
- `give_examples`
- `simplify`
- `summarize`
- `generate_questions`

Each config contains:
- `action_type`: The action identifier
- `system_instruction`: Base prompt (admin-only)
- `version`: Auto-incremented on changes
- `is_active`: Whether this config is active

**TutorXUserInstructionsDefaults** (for each action type):
- `action_type`: The action identifier
- `default_user_instruction`: Default template (admin-managed)
- `version`: Auto-incremented on changes
- `is_active`: Whether this default is active

**Management Command**: Run `python manage.py init_tutorx_prompts` to initialize defaults.

### 2. User Customization (Optional)

Users can customize their instructions through the frontend API:

**Flow**:
1. **Frontend loads user instruction**: `GET /api/settings/tutorx-instructions/<action_type>/`
   - **Backend checks**: Does `UserTutorXInstruction` exist for this user + action_type?
   - **If exists**: Returns the existing instruction (customized or default)
   - **If doesn't exist (null)**:
     - Fetches default from `TutorXUserInstructionsDefaults`
     - Creates new `UserTutorXInstruction` with that default
     - Saves to database
     - Returns the newly created instruction
   - **Result**: Frontend always receives a populated instruction (never null/empty)
2. **User can edit instruction** in UI
3. **User performs action**: `POST /api/tutorx/blocks/<action_type>/`
   - Sends `user_prompt` in request
   - If `user_prompt_changed = true`: Backend saves to `UserTutorXInstruction`
4. **Next time**: User's saved instruction is loaded automatically (from step 1)

### 3. AI Service Usage

When `TutorXAIService` methods are called:

```python
service = TutorXAIService()

# Service receives user_prompt as parameter
result = service.explain_more(
    block_content="Python is a programming language",
    block_type="text",
    user_prompt="Please explain {block_content} using simple language...",  # From request
    context={"target_audience": "ages 8-12"}
)
```

**Internal Flow**:
1. Load system instruction from `TutorXBlockActionConfig` (admin-managed)
2. Use `user_prompt` from parameter (passed from view)
3. If `user_prompt` is None: Load default from `TutorXUserInstructionsDefaults`
4. Combine: System Instruction + User Prompt + Block Content + Context
5. Send to Gemini API

**Note**: The service does NOT access `UserTutorXInstruction` directly. Views handle loading/saving user instructions.

## Database Models

### TutorXBlockActionConfig

```python
{
    "action_type": "explain_more",
    "display_name": "Explain More",
    "description": "Expand on block content with more detail",
    "system_instruction": "You are an expert educational assistant...",  # Admin-only
    "version": 1,
    "is_active": True,
    "created_at": "...",
    "updated_at": "...",
    "created_by": <User>,
    "last_modified_by": <User>
}
```

### TutorXUserInstructionsDefaults

```python
{
    "action_type": "explain_more",
    "display_name": "Explain More",
    "description": "Default instruction template",
    "default_user_instruction": "Please explain {block_content}...",  # Admin-managed template
    "version": 1,
    "is_active": True,
    "created_at": "...",
    "updated_at": "...",
    "created_by": <User>,
    "last_modified_by": <User>
}
```

### UserTutorXInstruction

```python
{
    "id": "uuid",
    "user": <User>,
    "action_type": "explain_more",
    "user_instruction": "Please explain {block_content} using simple language...",  # User-customizable
    "created_at": "...",
    "updated_at": "..."
}
```

## Frontend Integration

### User Instruction Field

Users should have a field in the frontend where they can:
1. **View** their current instruction for each action type
2. **Edit** their instruction
3. **Save** their instruction (via `user_prompt_changed` flag or separate API call)
4. **Reset** to default

**Example UI**:
```
┌─────────────────────────────────────────┐
│ Explain More - Custom Instruction        │
├─────────────────────────────────────────┤
│ [Text Area]                              │
│ Please explain {block_content} in a     │
│ way that uses simple language...         │
│                                          │
│ [✓] Save this instruction                │
│ [Reset to Default]                       │
└─────────────────────────────────────────┘
```

### API Endpoints

1. **GET** `/api/settings/tutorx-instructions/<action_type>/` - Get user instruction (creates with default if doesn't exist)
2. **PUT** `/api/settings/tutorx-instructions/<action_type>/` - Update user instruction
3. **POST** `/api/settings/tutorx-instructions/<action_type>/` - Reset to default
4. **POST** `/api/tutorx/blocks/<action_type>/` - Perform action (saves instruction if `user_prompt_changed = true`)

## Complete Flow Example

### Admin Creates Base Prompts

**Django Admin** → `TutorXBlockActionConfig`:
- Action Type: `explain_more`
- System Instruction: `"You are an expert educational assistant..."`

**Django Admin** → `TutorXUserInstructionsDefaults`:
- Action Type: `explain_more`
- Default User Instruction: `"Please explain {block_content} using simple language..."`

### User First Time

**Frontend** → `GET /api/settings/tutorx-instructions/explain_more/`:
- **Backend**: Checks if `UserTutorXInstruction` exists → No (first time)
- **Backend**: Fetches default from `TutorXUserInstructionsDefaults`
- **Backend**: Creates new `UserTutorXInstruction` with default
- **Backend**: Saves to database
- **Response**: Returns the newly created instruction with default
- **User sees**: Default instruction in UI (populated, ready to edit)

**User edits** instruction:
```
Please explain {block_content} using simple language for ages 8-12.
Include real-world examples.
```

### User Performs Action

**Frontend** → `POST /api/tutorx/blocks/explain_more/`:
```json
{
    "block_content": "Variables store data",
    "block_type": "text",
    "user_prompt": "Please explain {block_content} using simple language for ages 8-12...",
    "user_prompt_changed": true,
    "context": {"target_audience": "ages 8-12"}
}
```

**Backend**:
1. Validates request
2. Saves `user_prompt` to `UserTutorXInstruction` (because `user_prompt_changed = true`)
3. Loads `system_instruction` from `TutorXBlockActionConfig`
4. Calls `TutorXAIService.explain_more()` with:
   - `system_instruction`: "You are an expert educational assistant..."
   - `user_prompt`: "Please explain Variables store data using simple language for ages 8-12..."
   - `block_content`: "Variables store data"
   - `context`: {"target_audience": "ages 8-12"}

**Service**:
1. Builds combined prompt
2. Sends to Gemini API
3. Returns explanation

### Next Time User Loads Page

**Frontend** → `GET /api/settings/tutorx-instructions/explain_more/`:
- Response: User's saved custom instruction
- User sees their custom instruction (not default)

## Benefits

1. **Consistency**: Base system instructions ensure consistent AI behavior
2. **Flexibility**: Users can customize instructions to their needs
3. **Version Control**: System instructions and defaults are versioned
4. **Admin Control**: Admins can update base prompts without code changes
5. **User Personalization**: Users can tailor AI responses to their teaching/learning style
6. **Clean Separation**: Service layer focused on AI, views handle data persistence
7. **Default Templates**: New users get helpful defaults, can customize as needed

## Key Design Decisions

1. **Service Layer**: `TutorXAIService` receives `user_prompt` as parameter, doesn't access DB directly
2. **View Layer**: Views handle loading/saving `UserTutorXInstruction`
3. **Settings App**: User instructions stored in `settings` app (consistent with other user settings)
4. **TutorX App**: System instructions and defaults stored in `tutorx` app (admin-managed)
5. **Hybrid Approach**: Frontend sends `user_prompt` with each request, backend saves if `user_prompt_changed = true`

## Migration Path

1. **Initial Setup**: Run `python manage.py init_tutorx_prompts` to create default configs
2. **Default Behavior**: New users get default instructions from `TutorXUserInstructionsDefaults`
3. **User Adoption**: Users gradually customize instructions as needed
4. **Updates**: Admins can update system instructions and defaults without affecting user customizations
