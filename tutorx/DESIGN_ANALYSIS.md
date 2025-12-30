# TutorX Prompt Design Analysis

## Recommended Design: Hybrid Approach with Default Prompts

### Core Concept

1. **Default User Prompt**: Always available, always sent with request
2. **Flag `user_prompt_changed`**: Indicates if user wants to save customization
3. **Most cases**: Use prompt as received (no DB write)
4. **When customized**: Save to DB only when user explicitly wants to persist

### Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Frontend (Page Load)                                        │
├─────────────────────────────────────────────────────────────┤
│ 1. Load default prompt (from config or hardcoded)           │
│ 2. Optionally load user's saved prompt (if exists)          │
│ 3. Display prompt in UI with "Customize" checkbox           │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ User Action (Explain More, etc.)                            │
├─────────────────────────────────────────────────────────────┤
│ Frontend sends:                                              │
│ {                                                           │
│   block_content: "...",                                     │
│   user_prompt: "default or custom text",                    │
│   user_prompt_changed: false  // true if user customized   │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ Backend Service                                             │
├─────────────────────────────────────────────────────────────┤
│ 1. Load system instruction from DB                          │
│ 2. Use user_prompt from request (no DB load needed)         │
│ 3. If user_prompt_changed = true:                           │
│    → Save to TutorXUserPrompt DB                            │
│ 4. Combine and send to AI                                   │
└─────────────────────────────────────────────────────────────┘
```

## Benefits of This Approach

### ✅ Performance
- **No DB read** for user prompt on every request (most users use default)
- **No DB write** unless user explicitly customizes
- **Fast**: Just use prompt from request

### ✅ Flexibility
- User can customize prompt on-the-fly
- User can test different prompts without saving
- User can save when satisfied

### ✅ Simplicity
- Frontend always sends prompt (no conditional logic)
- Backend just uses what it receives
- Only saves when flag is true

### ✅ User Experience
- Default prompt always available (no empty state)
- User can see and edit prompt before using
- Clear workflow: Edit → Use → Save (optional)

## Implementation Details

### Frontend Behavior

```javascript
// On page load
const defaultPrompt = "Please explain {block_content} in detail...";
const savedPrompt = await loadUserPrompt('explain_more'); // Optional
const currentPrompt = savedPrompt || defaultPrompt;

// User can edit
const [prompt, setPrompt] = useState(currentPrompt);
const [isCustomized, setIsCustomized] = useState(!!savedPrompt);

// When user clicks "Explain More"
const handleExplainMore = async () => {
  await fetch('/api/tutorx/actions/explain-more/', {
    method: 'POST',
    body: JSON.stringify({
      block_content: "...",
      user_prompt: prompt,
      user_prompt_changed: isCustomized  // true if user edited
    })
  });
};
```

### Backend Service

```python
def explain_more(
    self,
    block_content: str,
    user_prompt: str,  # Always sent from frontend
    user_prompt_changed: bool = False,  # Flag
    user_id: Optional[int] = None,  # To save if changed
    ...
):
    # Load system instruction from DB
    system_instruction = self._get_system_instruction('explain_more')
    
    # Use user_prompt from request (no DB load)
    prompt = self._build_prompt(..., user_prompt_text=user_prompt)
    
    # Save to DB only if user customized
    if user_prompt_changed and user_id:
        self._save_user_prompt('explain_more', user_id, user_prompt)
    
    # Generate AI response
    response = self.gemini_service.generate(...)
    return response
```

## Default Prompt Source

### Option 1: Hardcoded in Frontend
```javascript
const DEFAULT_PROMPTS = {
  explain_more: "Please explain {block_content} in detail...",
  give_examples: "Provide examples for {block_content}...",
  // ...
};
```

**Pros**: Simple, no API call needed  
**Cons**: Can't be updated without frontend deploy

### Option 2: Config Endpoint
```javascript
// GET /api/tutorx/prompts/defaults/
const defaults = await fetch('/api/tutorx/prompts/defaults/');
```

**Pros**: Can be updated by admin  
**Cons**: Extra API call

### Option 3: Admin-Managed Defaults (Recommended)
Add `default_user_prompt` field to `TutorXBlockActionConfig`:

```python
class TutorXBlockActionConfig(models.Model):
    system_instruction = models.TextField(...)  # Admin-only
    default_user_prompt = models.TextField(...)  # Default for users
```

**Pros**: 
- Admins can set defaults
- Consistent with system instruction pattern
- Can be versioned

**Cons**: Slightly more complex

## Database Model Updates

### Current: TutorXUserPrompt
- Stores user's custom prompt
- Only created when `user_prompt_changed = true`

### Optional: Add default to TutorXBlockActionConfig
```python
class TutorXBlockActionConfig(models.Model):
    # ... existing fields ...
    default_user_prompt = models.TextField(
        help_text="Default user prompt template. Users see this initially."
    )
```

## API Design

### Action Endpoint
```http
POST /api/tutorx/actions/explain-more/
{
  "block_content": "...",
  "user_prompt": "Please explain...",  // Always sent
  "user_prompt_changed": false,        // true if customized
  "context": {...}
}
```

### Optional: Get Defaults Endpoint
```http
GET /api/tutorx/prompts/defaults/
Response: {
  "explain_more": "Default prompt...",
  "give_examples": "Default prompt...",
  ...
}
```

### Optional: Get User's Saved Prompt
```http
GET /api/tutorx/prompts/explain-more/
Response: {
  "user_prompt": "User's saved prompt...",
  "exists": true
}
```

## Comparison with Alternatives

| Approach | DB Reads | DB Writes | Flexibility | Complexity |
|----------|----------|-----------|------------|-----------|
| **Current (Frontend sends)** | 0 | 0 | High | Medium |
| **Backend loads** | 1 per request | 0 | Medium | Low |
| **Hybrid (Recommended)** | 0 | Only when changed | High | Low |

## Recommendation

✅ **Use Hybrid Approach**:
1. Frontend always sends `user_prompt` (default or custom)
2. Frontend sends `user_prompt_changed` flag
3. Backend uses prompt as received (no DB read)
4. Backend saves to DB only if `user_prompt_changed = true`

### Why This Works Best

1. **Performance**: No DB overhead for most requests
2. **Flexibility**: User can customize on-the-fly
3. **Simplicity**: Clear, predictable flow
4. **User Control**: User decides when to save
5. **Scalability**: Minimal database operations

## Implementation Checklist

- [ ] Update service methods to accept `user_prompt` and `user_prompt_changed`
- [ ] Add `_save_user_prompt()` method (only called when flag is true)
- [ ] Remove `_get_user_prompt()` method (no longer needed)
- [ ] Add `default_user_prompt` to `TutorXBlockActionConfig` (optional)
- [ ] Update management command to include default prompts
- [ ] Create API endpoint for getting defaults (optional)
- [ ] Update frontend to always send prompt with flag
