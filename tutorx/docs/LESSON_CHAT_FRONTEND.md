# Lesson Chat: Frontend Integration Instructions

This document gives step-by-step instructions for connecting your frontend to the lesson chat API so students can send messages and see text replies, Q&A blocks, or explainer-image payloads.

---

## 1. Endpoint and authentication

- **URL:** `POST /api/tutorx/lessons/{lessonId}/chat/`
- **Base URL:** Use your API base (e.g. `https://your-api.com` or relative `/api/tutorx/lessons/...`).
- **Auth:** Send the user’s auth token in the request (e.g. `Authorization: Bearer <token>` or your app’s header). Same as other TutorX endpoints (e.g. lesson content, ask).
- **CORS:** Backend must allow your frontend origin for this endpoint (same as rest of API).

---

## 2. Request format

Send a JSON body with two fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | Yes | The student’s message. Must be non-empty after trim. |
| `conversation` | array | No | List of previous messages in this chat. Omit or send `[]` for the first message. |

**Conversation item shape**

Each element in `conversation` is an object:

- **User message:** `{ "role": "user", "content": "<text>" }`
- **Assistant message:**  
  - Text: `{ "role": "assistant", "type": "text", "content": "<text>" }`  
  - Q&A: `{ "role": "assistant", "type": "qanda", "data": { "questions": [...], "message": "..." } }`  
  - Explainer image: `{ "role": "assistant", "type": "explainer_image", "data": { "image_description": "...", "image_prompt": "..." } }`

**Example request (first message):**

```json
{
  "message": "I don't understand this phrase",
  "conversation": []
}
```

**Example request (follow-up):**

```json
{
  "message": "Give me some practice questions",
  "conversation": [
    { "role": "user", "content": "I don't understand this phrase" },
    { "role": "assistant", "type": "text", "content": "Here's a simpler way to think about it: ..." }
  ]
}
```

---

## 3. Response format

Every successful response (200) has:

| Field | Type | Description |
|-------|------|-------------|
| `response_type` | string | One of: `"text"`, `"qanda"`, `"explainer_image"`. Use this to choose how to render the **latest** reply. |
| `content` | string | Present when `response_type === "text"`. Plain text or markdown. |
| `data` | object | Present when `response_type === "qanda"` or `"explainer_image"`. Structure depends on `response_type` (see below). |
| `conversation` | array | Full thread: previous messages plus the new user message and the new assistant message. Use this to render the whole chat and to send back as `conversation` on the next request. |

**When `response_type === "text"`**

- Use `content` for the latest message.
- The new assistant message in `conversation` will be `{ "role": "assistant", "type": "text", "content": "<same string>" }`.

**When `response_type === "qanda"`**

- Use `data` for the latest message. It has:
  - `questions`: array of question objects (see schema below).
  - `message`: string (e.g. "Do you want harder questions?").
- The new assistant message in `conversation` will be `{ "role": "assistant", "type": "qanda", "data": { "questions", "message" } }`.

**When `response_type === "explainer_image"`**

- Use `data` for the latest message. It has:
  - `image_description`: string (e.g. for alt text).
  - `image_prompt`: string (e.g. for an image generation API or placeholder).
- The new assistant message in `conversation` will be `{ "role": "assistant", "type": "explainer_image", "data": { "image_description", "image_prompt" } }`.

**Q&A question object (for `data.questions`)**

Each item can look like:

- `question_text`: string  
- `type`: e.g. `"multiple_choice"`, `"true_false"`, `"short_answer"`, `"essay"`, `"fill_blank"`  
- `difficulty`: e.g. `"easy"`, `"medium"`, `"hard"`  
- `content`: object with e.g. `options`, `correct_answer`, `instructions`, `blanks`, `correct_answers` depending on `type`  
- `explanation`: optional string  

Render these with your existing Q&A/quiz UI (e.g. show question, then “Show answer” to reveal `correct_answer` and `explanation`).

---

## 4. How to use the response in the UI

1. **Store the full thread**  
   After each successful response, set your chat state to `response.conversation` (or append the two new messages if you prefer). Send that full list as `conversation` on the next request.

2. **Render the latest reply**  
   Use `response_type` to pick the template for the **new** message:
   - `response_type === "text"` → render `content` (e.g. in a message bubble, with markdown if you support it).
   - `response_type === "qanda"` → render `data` with your Q&A component (list of questions + `data.message`).
   - `response_type === "explainer_image"` → render `data.image_description` and/or `data.image_prompt` (e.g. placeholder, or call an image API later).

3. **Rendering history**  
   When rendering past messages from `conversation`, use each assistant message’s `type` (and `content` or `data`) the same way: `type === "text"` → show `content`; `type === "qanda"` → show Q&A from `data`; `type === "explainer_image"` → show image block from `data`.

---

## 5. Example: fetch and state update (JavaScript/TypeScript)

Assume you have:

- `lessonId`: UUID of the TutorX lesson  
- `apiBase`: base URL for the API  
- `getAuthHeader()`: returns your auth header object (e.g. `{ Authorization: 'Bearer ' + token }`)

```javascript
async function sendLessonChatMessage(lessonId, message, conversation = []) {
  const url = `${apiBase}/api/tutorx/lessons/${lessonId}/chat/`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    },
    body: JSON.stringify({ message, conversation }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || err.detail || 'Chat request failed');
  }
  return res.json();
}

// Usage in React (example state + handler):
// State: conversation (array), input (string), loading (bool)
function LessonChat({ lessonId }) {
  const [conversation, setConversation] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || loading) return;
    setLoading(true);
    setInput('');
    try {
      const response = await sendLessonChatMessage(lessonId, msg, conversation);
      setConversation(response.conversation);
    } catch (e) {
      console.error(e);
      // Show error to user
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <MessageList conversation={conversation} />
      <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && handleSend()} />
      <button onClick={handleSend} disabled={loading}>Send</button>
    </div>
  );
}
```

---

## 6. Example: rendering by `response_type` and message `type`

```javascript
function MessageList({ conversation }) {
  return (
    <div className="message-list">
      {conversation.map((msg, i) => (
        <div key={i} className={msg.role === 'user' ? 'user' : 'assistant'}>
          {msg.role === 'user' && <p>{msg.content}</p>}
          {msg.role === 'assistant' && (
            <>
              {msg.type === 'text' && <div className="text-message">{renderMarkdown(msg.content)}</div>}
              {msg.type === 'qanda' && <QandABlock questions={msg.data?.questions} message={msg.data?.message} />}
              {msg.type === 'explainer_image' && (
                <ExplainerImageBlock
                  description={msg.data?.image_description}
                  prompt={msg.data?.image_prompt}
                />
              )}
            </>
          )}
        </div>
      ))}
    </div>
  );
}
```

Use the same branching for the **latest** reply: if you store `response_type` and `content`/`data` separately, render the latest assistant message with the same logic (`response_type` → text vs qanda vs explainer_image).

---

## 7. Error handling

- **400 Bad Request:** Invalid body (e.g. missing or empty `message`). Show a validation message.
- **403 Forbidden:** User is not the course teacher or an enrolled student. Show “You don’t have access to this lesson.”
- **404 Not Found:** Lesson not found or not a TutorX lesson. Show “Lesson not available.”
- **500 Internal Server Error:** Backend or AI error. Show a generic “Something went wrong” and optionally retry.

Parse error body as JSON when possible; backend may send `{ "error": "..." }` or similar.

---

## 8. Checklist for frontend

- [ ] Call `POST /api/tutorx/lessons/{lessonId}/chat/` with JSON `{ message, conversation }`.
- [ ] Send auth header (same as other TutorX endpoints).
- [ ] After 200, replace (or extend) chat state with `response.conversation`.
- [ ] For the latest reply, use `response.response_type` to choose template and read `response.content` (text) or `response.data` (qanda / explainer_image).
- [ ] When rendering history, use each assistant message’s `type` and `content` or `data` with the same three templates.
- [ ] Handle 400, 403, 404, 500 and show appropriate messages.

For more backend context (tools, schemas, handlers), see `LESSON_CHAT_TUTORIAL.md`. For the API summary, see `API_REFERENCE.md` (lesson chat section).
