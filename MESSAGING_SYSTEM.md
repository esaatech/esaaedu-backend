# Teacher-Parent-Student Messaging System

## Overview

A conversation-based messaging system that enables communication between teachers and parents/students. Messages are organized into conversation threads, with separate threads for parent and student communications.

## Architecture

### Design Decisions

1. **Conversation Threading**: Messages are grouped into conversations (one per teacher-student-recipient_type combination)
2. **Recipient Type Flag**: Supports both parent and student messaging via `recipient_type` field
3. **Student Profile Link**: All conversations are linked to `StudentProfile`, but students cannot see parent-type conversations
4. **REST API First**: Initial implementation uses REST API, designed for future WebSocket conversion
5. **No Student UI Initially**: Student messaging UI will be added later

### Conversation Structure (ASCII Diagram)

Each unique combination of (Teacher, Student, Recipient Type) creates exactly ONE conversation:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CONVERSATION STRUCTURE                            │
└─────────────────────────────────────────────────────────────────────┘

Teacher A ──┐
            ├──> Conversation 1 (Teacher A + Student 1 + parent)
Student 1 ──┤    └──> Messages: [msg1, msg2, msg3, ...]
            │
            ├──> Conversation 2 (Teacher A + Student 1 + student)
            │    └──> Messages: [msg1, msg2, ...]
            │
            ├──> Conversation 3 (Teacher A + Student 2 + parent)
Student 2 ──┤    └──> Messages: [msg1, msg2, ...]
            │
            └──> Conversation 4 (Teacher A + Student 2 + student)
                 └──> Messages: [msg1, ...]

Teacher B ──┐
            ├──> Conversation 5 (Teacher B + Student 1 + parent)
Student 1 ──┤    └──> Messages: [msg1, msg2, ...]
            │
            └──> Conversation 6 (Teacher B + Student 1 + student)
                 └──> Messages: [msg1, ...]

Teacher B ──┐
            └──> Conversation 7 (Teacher B + Student 3 + parent)
Student 3 ──┘    └──> Messages: [msg1, msg2, msg3, ...]


KEY POINTS:
═══════════════════════════════════════════════════════════════════════

1. ONE conversation per unique (Teacher, Student, Recipient Type) combination
   ───────────────────────────────────────────────────────────────────
   Teacher A + Student 1 + parent    → Conversation 1 (unique)
   Teacher A + Student 1 + student   → Conversation 2 (unique)
   Teacher A + Student 2 + parent    → Conversation 3 (unique)
   Teacher B + Student 1 + parent    → Conversation 5 (unique)
   Teacher B + Student 1 + student   → Conversation 6 (unique)

2. Each conversation contains multiple messages
   ───────────────────────────────────────────────────────────────────
   Conversation 1: [Message 1, Message 2, Message 3, ...]
   Conversation 2: [Message 1, Message 2, ...]
   Conversation 3: [Message 1, Message 2, ...]

3. Parent and Student conversations are SEPARATE
   ───────────────────────────────────────────────────────────────────
   Teacher A + Student 1 + parent   → Separate conversation
   Teacher A + Student 1 + student   → Separate conversation
   
   Parents can ONLY see parent-type conversations
   Students can ONLY see student-type conversations (when implemented)

4. Multiple teachers can have conversations with the same student
   ───────────────────────────────────────────────────────────────────
   Teacher A + Student 1 + parent   → Conversation 1
   Teacher B + Student 1 + parent   → Conversation 5 (different teacher)
   
   Each teacher has their own conversation thread with the student/parent


DATABASE CONSTRAINT:
═══════════════════════════════════════════════════════════════════════

unique_together = ['student_profile', 'teacher', 'recipient_type']

This ensures:
- No duplicate conversations for the same (teacher, student, recipient_type)
- Each combination creates exactly ONE conversation record
- Attempting to create a duplicate returns the existing conversation


EXAMPLE SCENARIO:
═══════════════════════════════════════════════════════════════════════

Teacher: Ms. Smith
Student: John Doe
Recipient Types: 'parent' and 'student'

Result:
  ┌─────────────────────────────────────────────────────────────┐
  │ Conversation A: Ms. Smith ↔ John's Parent                     │
  │   - recipient_type: 'parent'                                 │
  │   - Messages visible to: Teacher & Parent                    │
  │   - Messages NOT visible to: Student                         │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │ Conversation B: Ms. Smith ↔ John (Student)                   │
  │   - recipient_type: 'student'                                │
  │   - Messages visible to: Teacher & Student                    │
  │   - Messages NOT visible to: Parent                          │
  └─────────────────────────────────────────────────────────────┘

These are TWO separate conversations, even though they involve the same
teacher and student, because they have different recipient_type values.
```

## Database Models

### Conversation Model

**Location**: `student/models.py`

**Purpose**: Represents a conversation thread between a teacher and a student's parent or the student themselves.

**Fields**:
- `id`: UUID (primary key)
- `student_profile`: ForeignKey to StudentProfile
- `teacher`: ForeignKey to User (must be a teacher)
- `recipient_type`: CharField - 'parent' or 'student'
- `subject`: CharField (optional) - Conversation topic/subject
- `created_at`: DateTimeField - When conversation was created
- `updated_at`: DateTimeField - Last update timestamp
- `last_message_at`: DateTimeField - Timestamp of most recent message (for sorting)

**Constraints**:
- Unique together: `['student_profile', 'teacher', 'recipient_type']` - One conversation per teacher-student-recipient_type combination
- Indexes:
  - `['student_profile', 'recipient_type', '-last_message_at']` - For listing conversations
  - `['teacher', 'recipient_type', '-last_message_at']` - For teacher's conversation list

### Message Model

**Location**: `student/models.py`

**Purpose**: Individual messages within a conversation.

**Fields**:
- `id`: UUID (primary key)
- `conversation`: ForeignKey to Conversation
- `sender`: ForeignKey to User - Who sent the message
- `content`: TextField - Message content
- `created_at`: DateTimeField - When message was sent
- `read_at`: DateTimeField - When message was read (null if unread)
- `read_by`: ForeignKey to User - Who read the message (null if unread)

**Constraints**:
- Indexes:
  - `['conversation', '-created_at']` - For listing messages in conversation
  - `['conversation', 'read_at']` - For unread count queries
- Default ordering: `['created_at']` - Chronological order

## API Endpoints

### Teacher Endpoints

**Base URL**: `/api/teacher/`

#### 1. List Conversations for a Student
```
GET /api/teacher/students/{student_id}/conversations/
```

**Query Parameters**:
- `recipient_type` (optional): Filter by 'parent' or 'student'. If not provided, returns all.

**Response**:
```json
{
  "conversations": [
    {
      "id": "uuid",
      "student_profile_id": "uuid",
      "student_name": "John Doe",
      "recipient_type": "parent",
      "subject": "Homework Progress",
      "last_message_at": "2025-01-15T10:30:00Z",
      "unread_count": 2,
      "last_message_preview": "Thanks for the update!"
    }
  ]
}
```

**Permissions**: Teacher must teach the student (student must be in teacher's classes)

#### 2. Create/Get Conversation
```
POST /api/teacher/students/{student_id}/conversations/
```

**Request Body**:
```json
{
  "recipient_type": "parent",  // or "student"
  "subject": "Optional subject line"
}
```

**Response**: Conversation object (creates if doesn't exist, returns existing if found)

#### 3. Get Messages in Conversation
```
GET /api/teacher/conversations/{conversation_id}/messages/
```

**Query Parameters**:
- `page` (optional): Page number for pagination
- `page_size` (optional): Messages per page (default: 50)

**Response**:
```json
{
  "conversations": {
    "id": "uuid",
    "student_name": "John Doe",
    "recipient_type": "parent",
    "subject": "Homework Progress"
  },
  "messages": [
    {
      "id": "uuid",
      "sender_id": "uuid",
      "sender_name": "Teacher Name",
      "sender_type": "teacher",
      "content": "Message content",
      "created_at": "2025-01-15T10:30:00Z",
      "read_at": "2025-01-15T11:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_pages": 1,
    "total_count": 5
  }
}
```

#### 4. Send Message
```
POST /api/teacher/conversations/{conversation_id}/messages/
```

**Request Body**:
```json
{
  "content": "Message content here"
}
```

**Response**: Created message object

#### 5. Mark Message as Read
```
PATCH /api/teacher/messages/{message_id}/read/
```

**Response**: Updated message object with `read_at` timestamp

#### 6. Get Unread Count
```
GET /api/teacher/conversations/unread-count/
```

**Query Parameters**:
- `recipient_type` (optional): Filter by 'parent' or 'student'

**Response**:
```json
{
  "total_unread": 5,
  "by_recipient_type": {
    "parent": 3,
    "student": 2
  }
}
```

### Parent Endpoints

**Base URL**: `/api/student/parent/`

**Note**: All parent endpoints automatically filter to `recipient_type='parent'` conversations only.

#### 1. List Conversations
```
GET /api/student/parent/dashboard/conversations/
```

**Response**: Same format as teacher's list conversations, but only parent-type conversations

#### 2. Get Messages in Conversation
```
GET /api/student/parent/conversations/{conversation_id}/messages/
```

**Response**: Same format as teacher's get messages

#### 3. Send Message
```
POST /api/student/parent/conversations/{conversation_id}/messages/
```

**Request Body**:
```json
{
  "content": "Message content here"
}
```

#### 4. Mark Message as Read
```
PATCH /api/student/parent/messages/{message_id}/read/
```

#### 5. Get Unread Count
```
GET /api/student/parent/dashboard/messages/unread-count/
```

**Response**:
```json
{
  "unread_count": 3
}
```

### Student Endpoints (Future - Not Implemented Initially)

**Base URL**: `/api/student/`

**Note**: Will only show `recipient_type='student'` conversations. Implementation deferred.

## Permissions & Authorization

### Teacher Permissions
- Can create conversations with any student in their classes
- Can send/receive messages in conversations for students they teach
- Can view both parent and student type conversations
- Cannot access conversations for students not in their classes

### Parent Permissions
- Can only view/send messages in `recipient_type='parent'` conversations
- Can only access conversations for their own student
- Cannot see `recipient_type='student'` conversations
- Cannot access conversations for other students

### Student Permissions (Future)
- Can only view/send messages in `recipient_type='student'` conversations
- Can only access conversations for their own profile
- Cannot see `recipient_type='parent'` conversations

## Business Logic

### Conversation Creation
1. When sending first message, check if conversation exists for `(teacher, student_profile, recipient_type)`
2. If exists, use existing conversation
3. If not exists, create new conversation
4. Update `last_message_at` timestamp on conversation

### Message Sending
1. Validate sender has permission to send in conversation
2. Create message linked to conversation
3. Update conversation's `last_message_at` timestamp
4. Set `read_at` to null (unread initially)
5. Return created message

### Read Receipts
1. When message is marked as read:
   - Set `read_at` to current timestamp
   - Set `read_by` to the user who read it
   - Update message object

### Unread Count
- Count messages where `read_at` is null
- Filter by conversation's `recipient_type` for parent/student separation
- Cache unread counts per user for performance (future optimization)

## Database Indexes

### Conversation Indexes
- `['student_profile', 'recipient_type', '-last_message_at']` - For listing student's conversations
- `['teacher', 'recipient_type', '-last_message_at']` - For listing teacher's conversations
- Unique constraint: `['student_profile', 'teacher', 'recipient_type']` - Prevent duplicates

### Message Indexes
- `['conversation', '-created_at']` - For listing messages chronologically
- `['conversation', 'read_at']` - For unread count queries

## Serializers

### ConversationSerializer
- Full conversation details with related student/teacher info
- Includes unread count
- Includes last message preview

### ConversationListSerializer
- Lightweight version for list views
- Only essential fields for performance

### MessageSerializer
- Full message details
- Includes sender information
- Includes read status

### CreateMessageSerializer
- Validates message content
- Ensures content is not empty
- Validates length limits

## Views

### Teacher Views (`teacher/views.py`)

1. **StudentConversationsListView**
   - List/create conversations for a student
   - Filter by recipient_type
   - Permission: Teacher must teach the student

2. **ConversationMessagesView**
   - Get messages in conversation
   - Send new message
   - Pagination support

3. **MarkMessageReadView**
   - Mark message as read
   - Update read_at and read_by fields

4. **UnreadCountView**
   - Get total unread count
   - Filter by recipient_type

### Parent Views (`student/views.py`)

1. **ParentConversationsListView**
   - List conversations for parent's student
   - Auto-filter to recipient_type='parent'

2. **ParentConversationMessagesView**
   - Get messages in conversation
   - Send new message
   - Permission: Must be parent of the student

3. **ParentMarkMessageReadView**
   - Mark message as read
   - Permission: Must be parent of the student

4. **ParentUnreadCountView**
   - Get unread count for parent
   - Auto-filter to recipient_type='parent'

5. **Update ParentDashboardView**
   - Include unread message count in dashboard response

## URL Patterns

### Teacher URLs (`teacher/urls.py`)
```python
path('students/<uuid:student_id>/conversations/', views.StudentConversationsListView.as_view()),
path('conversations/<uuid:conversation_id>/messages/', views.ConversationMessagesView.as_view()),
path('messages/<uuid:message_id>/read/', views.MarkMessageReadView.as_view()),
path('conversations/unread-count/', views.UnreadCountView.as_view()),
```

### Parent URLs (`student/urls.py`)
```python
path('parent/dashboard/conversations/', views.ParentConversationsListView.as_view()),
path('parent/conversations/<uuid:conversation_id>/messages/', views.ParentConversationMessagesView.as_view()),
path('parent/messages/<uuid:message_id>/read/', views.ParentMarkMessageReadView.as_view()),
path('parent/dashboard/messages/unread-count/', views.ParentUnreadCountView.as_view()),
```

## Migration Plan

1. Create models in `student/models.py`
2. Generate migration: `python manage.py makemigrations student`
3. Review migration file
4. Run migration: `python manage.py migrate`
5. Register models in admin: `student/admin.py`

## Future Enhancements

### WebSocket Support
- Conversation threading makes WebSocket implementation easier
- Can subscribe to specific conversation threads
- Real-time message delivery
- Real-time read receipts
- Typing indicators (future)

### Additional Features
- Message attachments (files, images)
- Message reactions/emojis
- Message search
- Conversation archiving
- Email notifications for new messages
- Push notifications (mobile app)

## Testing Considerations

### Test Cases Needed
1. Teacher can create conversation with student
2. Teacher can send message in conversation
3. Parent can view conversations for their student
4. Parent can send message in conversation
5. Parent cannot see student-type conversations
6. Student cannot see parent-type conversations (when student UI added)
7. Unread count is accurate
8. Read receipts work correctly
9. Pagination works for message lists
10. Permissions are enforced correctly

## Performance Considerations

1. **Pagination**: Limit messages per page (default 50)
2. **Indexes**: All queries use indexed fields
3. **Select Related**: Use `select_related` for foreign keys
4. **Caching**: Cache unread counts (future optimization)
5. **Lazy Loading**: Load messages on demand, not all at once

## Security Considerations

1. **Permission Checks**: Verify user has access to conversation before allowing operations
2. **Input Validation**: Sanitize message content
3. **Rate Limiting**: Prevent message spam (future)
4. **Content Moderation**: Filter inappropriate content (future)

## Admin Interface

Register both models in Django admin for:
- Viewing all conversations
- Viewing all messages
- Debugging issues
- Manual moderation if needed

---

## Frontend Implementation Plan: Teacher-Student Messaging UI

### 1. Component Architecture (Atomic Design)

#### Atoms
- `MessageBubble.tsx` - Individual message display
- `MessageInput.tsx` - Text input for composing messages
- `UnreadBadge.tsx` - Badge showing unread count
- `Avatar.tsx` - User avatar (reusable)
- `BreadcrumbItem.tsx` - Single breadcrumb link

#### Molecules
- `MessageItem.tsx` - Message bubble + sender info + timestamp
- `ConversationHeader.tsx` - Header with recipient info and actions
- `MessageInputBar.tsx` - Input field + send button + attachment (future)
- `BreadcrumbNav.tsx` - Full breadcrumb navigation
- `UnreadCountButton.tsx` - Button with unread badge overlay

#### Organisms
- `MessageThread.tsx` - Full conversation thread (list of messages + input)
- `ConversationList.tsx` - List of conversations (for multi-teacher scenarios)
- `MessagingContainer.tsx` - Main container with header + thread + input

#### Templates
- `MessagingPageTemplate.tsx` - Layout template (breadcrumbs + container)
- `StudentOverviewTemplate.tsx` - Updated to include message buttons

#### Pages
- `TeacherStudentMessagesPage.tsx` - Teacher viewing student/parent messages
- `ParentMessagesPage.tsx` - Parent viewing messages (future)
- `StudentMessagesPage.tsx` - Student viewing messages (future)

### 2. Data Fetching Strategy (SWR)

#### Hooks Structure
```
hooks/
  ├── useConversations.ts          # List conversations for student
  ├── useConversationMessages.ts   # Messages in a conversation
  ├── useUnreadCount.ts            # Unread message count
  ├── useSendMessage.ts            # Send message mutation
  ├── useMarkAsRead.ts             # Mark message as read mutation
```

#### SWR Keys
- `['conversations', studentId, recipientType]` - List conversations
- `['conversation-messages', conversationId]` - Messages in conversation
- `['unread-count', studentId, recipientType]` - Unread count
- `['teacher-unread-count']` - Teacher's total unread (for badge)

### 3. File Structure

```
src/
├── components/
│   ├── messaging/
│   │   ├── atoms/
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── MessageInput.tsx
│   │   │   ├── UnreadBadge.tsx
│   │   │   └── Avatar.tsx
│   │   ├── molecules/
│   │   │   ├── MessageItem.tsx
│   │   │   ├── ConversationHeader.tsx
│   │   │   ├── MessageInputBar.tsx
│   │   │   ├── BreadcrumbNav.tsx
│   │   │   └── UnreadCountButton.tsx
│   │   └── organisms/
│   │       ├── MessageThread.tsx
│   │       ├── ConversationList.tsx
│   │       └── MessagingContainer.tsx
│   └── teacher/
│       └── student/
│           └── StudentOverview.tsx (update to add buttons)
├── hooks/
│   └── messaging/
│       ├── useConversations.ts
│       ├── useConversationMessages.ts
│       ├── useUnreadCount.ts
│       ├── useSendMessage.ts
│       └── useMarkAsRead.ts
├── pages/
│   └── teacher/
│       └── student/
│           └── StudentMessagesPage.tsx
├── services/
│   └── api.ts (add messaging API functions)
└── types/
    └── messaging.ts (TypeScript interfaces)
```

### 4. Workflow & User Flow

#### Step 1: Student Overview Page
```
Student Overview
├── [Message Parent] (with badge if unread > 0)
└── [Message Student] (with badge if unread > 0)
```

#### Step 2: Click "Message Parent" or "Message Student"
- Check if conversation exists:
  - If exists → Navigate to conversation thread page
  - If doesn't exist → Create conversation, then navigate to thread page

#### Step 3: Conversation Thread Page
```
Breadcrumb: Home > Students > [Student Name] > Message Parent

┌─────────────────────────────────────────────┐
│ [← Back]  Conversation with Parent          │
├─────────────────────────────────────────────┤
│                                             │
│  [Loading Skeleton / Message List]         │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │ Teacher: Message content...         │   │
│  │ 10:30 AM                            │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │ Parent: Response...                 │   │
│  │ 11:00 AM                            │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  [Message Input]                           │
│  ┌─────────────────────────────────────┐   │
│  │ Type your message...        [Send]  │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

### 5. State Management

#### Local State (useState)
- `isSending` - Loading state for send button
- `messageText` - Current input text
- `scrollToBottom` - Auto-scroll trigger

#### SWR State
- Conversations list (cached)
- Messages in conversation (cached)
- Unread counts (cached, revalidate on focus)

#### Optimistic Updates
- When sending message: Add to local list immediately
- On success: SWR revalidates
- On error: Revert and show error

### 6. API Integration

#### API Functions (in `services/api.ts`)
```typescript
// Teacher endpoints
getStudentConversations(studentId, recipientType)
getConversationMessages(conversationId, page?)
createConversation(studentId, recipientType, subject?)
sendMessage(conversationId, content)
markMessageAsRead(messageId)
getTeacherUnreadCount(recipientType?)

// Parent endpoints (for future)
getParentConversations()
getParentUnreadCount()
```

### 7. Loading States

#### Skeleton Components
- `MessageThreadSkeleton.tsx` - Loading state for message list
- `ConversationListSkeleton.tsx` - Loading state for conversation list

#### Loading Behavior
- First load: Show skeleton
- Subsequent loads: Show cached data + loading indicator
- Background refresh: Silent revalidation

### 8. Unread Count Badge Logic

#### Button Badge Display
```typescript
// On Student Overview page
- Fetch unread counts for both recipient types
- Display badge if count > 0
- Badge shows number (e.g., "3" or "99+")
```

#### Badge Updates
- Real-time: Poll every 30 seconds (or use WebSocket later)
- On navigation: Revalidate unread counts
- After reading: Update badge immediately

### 9. Routing

#### Routes
```typescript
/teacher/students/:studentId/messages/parent
/teacher/students/:studentId/messages/student
```

#### Navigation
- From Student Overview → Message page
- Breadcrumb back → Student Overview
- Browser back → Works correctly

### 10. Reusability Strategy

#### Shared Components
- `MessageThread` - Used by teacher, parent, student
- `MessageItem` - Same component, different styling based on context
- `MessageInputBar` - Same component, different API endpoints

#### Context-Based Styling
```typescript
// Use context or props to determine styling
<MessageThread 
  variant="teacher" | "parent" | "student"
  apiEndpoint={...}
/>
```

### 11. Error Handling

#### Error States
- Network errors: Show retry button
- Permission errors: Show "Access denied" message
- Not found: Show "Conversation not found" with create option

### 12. Implementation Steps

1. **Phase 1: Core Components**
   - Create atom/molecule components
   - Create SWR hooks
   - Add API functions

2. **Phase 2: Student Overview Integration**
   - Add message buttons
   - Fetch unread counts
   - Add badge display

3. **Phase 3: Messaging Page**
   - Create messaging page template
   - Implement message thread component
   - Add send message functionality

4. **Phase 4: Polish**
   - Add loading states
   - Add error handling
   - Add optimistic updates
   - Add auto-scroll

5. **Phase 5: Testing & Refinement**
   - Test all flows
   - Optimize performance
   - Add accessibility features

### 13. Technical Considerations

#### Performance
- Pagination: Load 50 messages at a time
- Virtual scrolling: For long conversations (future)
- Debounce: Input validation

#### Accessibility
- Keyboard navigation
- Screen reader support
- Focus management

#### Mobile Responsiveness
- Responsive layout
- Touch-friendly buttons
- Mobile-optimized input

### 14. Design Decisions

#### Badge Display
- Show exact number up to 99
- Show "99+" for 100 or more

#### Auto-scroll
- Always scroll to bottom on initial load
- Auto-scroll when new messages arrive
- Manual scroll disables auto-scroll temporarily

#### Message Timestamps
- Relative time: "2 hours ago", "Yesterday", "3 days ago"
- Absolute time for older messages: "Nov 15, 2025"

#### Empty State
- Show friendly message: "No messages yet. Start the conversation!"
- Prompt to send first message

#### Multi-Teacher Handling
- If student has multiple teachers: Show conversation list first
- Allow creating new conversation with specific teacher
- If only one teacher: Go directly to conversation thread

