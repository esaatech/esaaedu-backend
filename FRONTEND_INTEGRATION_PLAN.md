# Frontend Integration Plan: AI Course Generation

## Overview
Add "Use AI" button to Course Basics step that opens a chat panel from the right. AI generates course fields and auto-populates the form.

## User Flow

```
1. User clicks "Use AI" button on Course Basics step
2. AI chat panel slides in from right
3. User types: "Create a course on Scratch programming for kids aged 8-12"
4. AI streams response in real-time
5. When complete, AI returns JSON with:
   - title
   - short_description
   - detailed_description
   - category
6. Auto-populate form fields
7. User can:
   - Click "Next" if happy → Continue to next step
   - Ask for changes: "Make description shorter" → AI refines
   - Continue chatting until satisfied
```

## Frontend Components Needed

### 1. WebSocket Hook (`src/hooks/useAICourseGeneration.ts`)
```typescript
- Connect to WebSocket
- Handle authentication
- Send messages
- Receive streaming responses
- Auto-populate form on completion
```

### 2. AI Chat Panel Component (`src/components/teacher/ai/AICourseGenerationPanel.tsx`)
```typescript
- Slides in from right
- Chat interface (input + messages)
- Shows streaming indicator
- Auto-populates form when complete
- Close button to dismiss
```

### 3. Integration in CourseCreationFlow
- Add "Use AI" button next to Course Title field
- State to control panel visibility
- Pass formData and setFormData to panel
- Panel updates form fields directly

## File Structure

```
src/
├── hooks/
│   └── useAICourseGeneration.ts
├── components/
│   └── teacher/
│       └── ai/
│           ├── AICourseGenerationPanel.tsx
│           ├── AIChatMessage.tsx
│           └── AIInput.tsx
└── components/teacher/sections/
    └── CourseCreationFlow.tsx (modified)
```

## WebSocket Message Format

### Client → Server
```typescript
// Auth
{ type: "auth", token: firebaseToken }

// Initial request
{ 
  type: "message", 
  content: "Create course on...",
  context: { age_range: "8-12", level: "beginner" }
}

// Refinement
{ 
  type: "refinement", 
  content: "Make description shorter" 
}
```

### Server → Client
```typescript
// Auth success
{ type: "auth_success", message: "..." }

// Processing
{ type: "processing", message: "Generating..." }

// Streaming chunk
{ type: "streaming", content: "..." }

// Complete
{ 
  type: "complete", 
  conversation_id: "uuid",
  data: {
    title: "...",
    short_description: "...",
    detailed_description: "...",
    category: "..."
  }
}

// Error
{ type: "error", message: "..." }
```

## Implementation Steps

### Step 1: Create WebSocket Hook
- Connect to `ws://your-api-domain/ws/ai/course-generation/`
- Handle authentication
- Manage connection state
- Expose: sendMessage, isConnected, messages, streaming

### Step 2: Create Chat Panel Component
- Slide-in animation from right
- Message list showing conversation
- Input field with send button
- Streaming indicator
- Auto-close on successful generation

### Step 3: Integrate with CourseCreationFlow
- Add "Use AI" button
- State: `showAIPanel`
- Pass formData/setFormData to panel
- Panel updates: title, description, long_description, category

### Step 4: Map AI Response to Form
```typescript
// When complete message received:
setFormData(prev => ({
  ...prev,
  title: data.title,
  description: data.short_description,
  long_description: data.detailed_description,
  category: data.category
}))
```

## Testing

1. Test WebSocket connection
2. Test authentication flow
3. Test message sending
4. Test streaming reception
5. Test form auto-population
6. Test refinement flow

## Next Steps

1. Create `useAICourseGeneration.ts` hook
2. Create `AICourseGenerationPanel.tsx` component
3. Add button to `CourseCreationFlow.tsx`
4. Test end-to-end flow

