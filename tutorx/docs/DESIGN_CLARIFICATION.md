# TutorX Prompt Design Clarification

> **Note**: This document was created during the design phase. For current implementation details, see:
> - `README.md` - Complete documentation
> - `PROMPT_ARCHITECTURE.md` - Updated architecture details

---

# TutorX Prompt Design Clarification

## Current Understanding vs. Intended Design

### Current Implementation (What We Have)

1. **System Instruction** (`TutorXBlockActionConfig.system_instruction`)
   - ✅ Same for everyone (admin-managed)
   - ✅ Loaded from DB by backend

2. **Default User Prompt** (`TutorXBlockActionConfig.default_user_prompt`)
   - ❓ Template that all users see initially
   - ❓ Sent from frontend with each request

3. **User Prompt** (`TutorXUserPrompt.user_prompt`)
   - ❓ User's custom prompt
   - ❓ Saved only when `user_prompt_changed = true`

### Intended Design (What You Want)

1. **System Instruction** (`TutorXBlockActionConfig.system_instruction`)
   - ✅ Same for everyone (admin-managed)
   - ✅ Loaded from DB by backend
   - **Status**: ✅ Correct

2. **Default User Prompt** (`TutorXBlockActionConfig.default_user_prompt`)
   - ✅ Template/starting point for NEW users
   - ✅ Used when user hasn't customized yet
   - **Status**: ✅ Correct (but needs clarification on usage)

3. **User Prompt** (`TutorXUserPrompt.user_prompt`)
   - ✅ **Per-user customization**
   - ✅ Each user has their own prompt
   - ✅ Loaded when user has customized
   - **Status**: ⚠️ Needs clarification on loading mechanism

## The Question: How Should User Prompts Work?

### Option A: Frontend Loads User Prompt (Current Approach)
```
Flow:
1. Frontend loads default_user_prompt (from API or config)
2. Frontend checks if user has saved prompt (GET /api/tutorx/prompts/{action_type}/)
3. If user has saved: Use user's prompt
4. If no saved: Use default
5. User can edit
6. When using action: Send user_prompt + user_prompt_changed flag
7. Backend saves if flag is true
```

**Pros**:
- User can see/edit prompt before using
- Flexible - can test without saving
- Frontend controls the flow

**Cons**:
- Requires API call to load user prompt
- Frontend must manage prompt state

### Option B: Backend Loads User Prompt (Alternative)
```
Flow:
1. Frontend just sends action request (no prompt management)
2. Backend loads:
   - System instruction from DB
   - User prompt from DB (if exists) OR default from DB
3. Backend combines and uses
4. User manages prompts in separate settings page
```

**Pros**:
- Consistent pattern (both loaded from DB)
- Simpler frontend
- No prompt in request body

**Cons**:
- User can't edit on-the-fly
- Requires settings page for prompt management

### Option C: Hybrid (Recommended Based on Your Description)
```
Flow:
1. Frontend loads user's saved prompt (if exists) OR default
2. User can edit in UI
3. Frontend sends:
   - user_prompt (always)
   - user_prompt_changed (true if user edited)
4. Backend:
   - Uses user_prompt from request
   - Saves to DB if user_prompt_changed = true
   - Next time: User's saved prompt is loaded
```

**This matches your description**:
- Default prompt: Starting point for new users
- User prompt: Customizable per user
- System instruction: Same for everyone

## Key Questions to Clarify

### 1. Where Should User Prompts Be Loaded?

**Question**: When a user opens the page, should:
- **A**: Frontend load their saved prompt from API? (current)
- **B**: Backend load it automatically? (alternative)

### 2. When Should User Prompts Be Saved?

**Question**: Should prompts be saved:
- **A**: Only when user explicitly wants to (checkbox/flag)? (current)
- **B**: Always when user edits? (alternative)
- **C**: In a separate settings page? (alternative)

### 3. Default vs. User Prompt Relationship

**Question**: Should `default_user_prompt`:
- **A**: Be a template that users see initially, then customize? (current)
- **B**: Be a fallback if user hasn't customized? (alternative)
- **C**: Be removed entirely, and users always start with empty? (alternative)

### 4. Frontend Behavior

**Question**: On page load, should frontend:
- **A**: Load default, then check if user has saved, then replace? (current)
- **B**: Just load user's saved (or default if none)? (simpler)

## Recommended Design (Based on Your Description)

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│ System Instruction (Same for Everyone)                  │
│ - Stored in: TutorXBlockActionConfig.system_instruction │
│ - Managed by: Admins only                              │
│ - Loaded by: Backend (from DB)                          │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Default User Prompt (Template for New Users)            │
│ - Stored in: TutorXBlockActionConfig.default_user_prompt│
│ - Managed by: Admins                                    │
│ - Used when: User hasn't customized yet                 │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ User Prompt (Customizable Per User)                      │
│ - Stored in: TutorXUserPrompt.user_prompt               │
│ - Managed by: Each user                                 │
│ - Used when: User has customized                        │
│ - One per user per action_type                          │
└─────────────────────────────────────────────────────────┘
```

### Flow

1. **First Time User**:
   - Frontend loads `default_user_prompt` from `TutorXBlockActionConfig`
   - User sees default prompt
   - User can edit
   - When using action: `user_prompt_changed = true` → Saved to `TutorXUserPrompt`

2. **Returning User (Has Customized)**:
   - Frontend loads user's saved prompt from `TutorXUserPrompt`
   - User sees their custom prompt
   - User can edit further
   - When using action: `user_prompt_changed = true` → Updated in `TutorXUserPrompt`

3. **Backend Processing**:
   - Loads system instruction from DB
   - Uses user_prompt from request (no DB read needed)
   - Saves to DB only if `user_prompt_changed = true`

### API Endpoints Needed

1. **GET** `/api/tutorx/prompts/defaults/` - Get all default prompts
2. **GET** `/api/tutorx/prompts/{action_type}/` - Get user's saved prompt (if exists)
3. **POST** `/api/tutorx/actions/{action_type}/` - Execute action with prompt

## What Needs to Change?

Based on your clarification, I think the current design is mostly correct, but we need to ensure:

1. ✅ **System Instruction**: Same for everyone (already correct)
2. ✅ **Default User Prompt**: Template in `TutorXBlockActionConfig` (already correct)
3. ⚠️ **User Prompt Loading**: Frontend should load user's saved prompt if exists
4. ⚠️ **User Prompt Saving**: Only save when user explicitly wants to (current flag approach)

The main question is: **Should frontend load user's saved prompt automatically, or should it always start with default?**

