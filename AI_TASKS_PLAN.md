# AI Course Generation - 3 Task Breakdown

## Task 1: Basic Chatbot (Easiest - Start Here)
**Goal**: Continuous chat functionality that works even after closing/reopening the panel

### Requirements:
- ✅ User sends message → Backend responds with echo + random number
- ✅ Conversation persists in database (AIConversation model)
- ✅ After closing/reopening panel, conversation continues
- ✅ Random number in response proves it's a real backend response (not cached)

### Test Cases:
1. Send "hello" → Get response with random number
2. Send "test" → Get different random number
3. Close panel
4. Reopen panel
5. Send "continue" → Should restore conversation and continue with new random number

### Implementation:
- Use `AIConversation` model to store messages
- Always include `conversation_id` in responses
- Frontend stores `conversationId` and sends it on reconnect
- Backend restores conversation if `conversation_id` is provided

---

## Task 2: Approve Button & Form Population
**Goal**: Button to approve AI-generated content and populate form fields

### Requirements:
- ✅ "Approve" button appears when AI generates course data
- ✅ Clicking approve populates form fields (title, description, long_description, category)
- ✅ Button only shows when valid course data exists
- ✅ After approval, chat can continue for refinements

### Implementation:
- Add `approved` state in frontend
- Show approve button when `generatedData` exists and is valid
- Call `onDataGenerated` callback with the data
- Optionally mark conversation as approved in backend

---

## Task 3: Gemini API Integration
**Goal**: Proper API call to Gemini with all parameters

### Requirements:
- ✅ Use correct Vertex AI API format
- ✅ Pass system_instruction properly
- ✅ Pass output_schema for structured response
- ✅ Handle streaming responses
- ✅ Parse JSON correctly (handle field name variations)

### Current Issues:
- Field name mismatch: AI returns `courseTitle` but we expect `title`
- Need to ensure prompt enforces correct schema
- Need proper error handling for API failures

### Implementation:
- Update prompt template to enforce exact field names
- Use `generate_structured_content` method if available
- Or ensure prompt explicitly asks for specific field names
- Add retry logic for API failures

---

## Testing Strategy

### Task 1 Testing:
```
1. Open panel → Connect
2. Send "hello" → Should get: "Hello! [ID: 1234]"
3. Send "test" → Should get: "Echo: test [ID: 5678]"
4. Close panel
5. Reopen panel (should restore conversation)
6. Send "continue" → Should get: "Continuing... [ID: 9012]"
```

### Task 2 Testing:
```
1. Generate course data
2. Verify approve button appears
3. Click approve
4. Verify form fields populated
5. Send refinement message
6. Verify new data can be approved
```

### Task 3 Testing:
```
1. Send course generation request
2. Verify API call with correct parameters
3. Verify response matches schema
4. Verify field names are correct
5. Test with different requests
```

