# Consumers Architecture Plan

## Overview
WebSocket consumers for Django Channels that handle AI chat conversations and content generation.

## Consumer Structure

### 1. BaseAIConsumer (Abstract Base)
- Handles WebSocket connection lifecycle
- Authentication (Firebase token validation)
- Error handling and logging
- Message routing

### 2. CourseGenerationConsumer
- **WebSocket Path**: `/ws/ai/course-generation/`
- **Purpose**: Generate course content (title, description, objectives, prerequisites)
- **Input Schema**: 
  ```json
  {
    "type": "message",
    "content": "Create course on Java",
    "conversation_id": "uuid-or-null",
    "context": {
      "age_range": "8-12",
      "level": "beginner",
      "category": "programming"
    }
  }
  ```
- **Output Schema**: Structured course data matching Course model

### 3. LessonContentConsumer
- **WebSocket Path**: `/ws/ai/lesson-content/`
- **Purpose**: Generate lesson descriptions, content, outlines
- **Input**: Lesson ID + course context
- **Output**: Lesson content structure

### 4. QuizQuestionsConsumer
- **WebSocket Path**: `/ws/ai/quiz-questions/`
- **Purpose**: Generate quiz questions (batch)
- **Input**: Lesson ID, question count, question types
- **Output**: Array of question objects

### 5. AssignmentQuestionsConsumer
- **WebSocket Path**: `/ws/ai/assignment-questions/`
- **Purpose**: Generate assignment questions
- **Input**: Assignment ID, question count, types
- **Output**: Array of assignment question objects

## Message Flow

```
1. Frontend connects → WebSocket opens
2. Frontend sends auth token in first message
3. Consumer validates token → Stores user in scope
4. Frontend sends generation request
5. Consumer loads/creates conversation
6. Consumer calls GeminiAgent
7. Service streams response → Consumer forwards chunks
8. Final response → Consumer saves to conversation
9. Frontend can send refinements → Loop back to step 4
```

## Message Types

### From Frontend:
- `auth`: Initial authentication message
- `message`: User message/content generation request
- `refinement`: Refinement request for existing conversation
- `save`: Accept and save generated content

### From Backend:
- `auth_success`: Authentication confirmed
- `auth_error`: Authentication failed
- `streaming`: Chunk of AI response (for typing indicator)
- `complete`: Final structured response
- `error`: Error message

## Conversation Management

- Each consumer manages conversation state
- Load existing conversation by conversation_id
- Create new conversation if conversation_id is null
- Store messages in AIConversation model
- Maintain context (course_id, lesson_id, etc.)

## Error Handling

- Invalid token → Close connection with error
- Gemini API failure → Send error message, keep connection
- Parsing failure → Send error, allow retry
- Network timeout → Retry logic in service layer

## Authentication Flow

```python
async def connect(self):
    # Wait for auth message
    # Validate Firebase token
    # Store user in scope
    # Send auth_success
```

## Implementation Order

1. BaseAIConsumer - Core functionality
2. CourseGenerationConsumer - Simplest use case
3. Test with simple course generation
4. Add other consumers one by one

