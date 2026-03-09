# Plan: Q&A thread representation and intelligent closing message

Two issues to address:

1. **Why the AI’s previous answer wasn’t (fully) in the thread**
2. **Why the AI returns a fixed “Do you want harder questions?” — guide behavior, not the exact response**

---

## 1. Why the AI’s previous answer wasn’t in the thread

### 1.1 What the backend does today

- **Response:** The view builds `updated_conversation = conversation + [user_msg, assistant_msg]`. For qanda, `assistant_msg` is `{"role": "assistant", "type": "qanda", "data": { "questions": [...], "message": "..." } }`. So the **full** assistant turn (including questions + closing message) **is** added to the conversation in the API response.
- **Next request:** The frontend is expected to send that full `conversation` (including the last assistant qanda message) on the next POST. If it does, the backend receives a list that contains the qanda turn.
- **What we send to the intent model:** In `_build_conversation_prompt` ([lesson_chat.py](tutorx/services/lesson_chat.py)), for assistant messages with `type == "qanda"` we only use:
  - `content = msg.get("data", {}).get("message")`  
  So we only append **the closing message string** (e.g. “Do you want harder questions?”) to the prompt. We do **not** represent that we already delivered N questions.

So:

- **If the frontend does not append the qanda assistant message** to its conversation state before sending the next request, the thread will be missing that turn entirely (e.g. “Student: generate practise questions” then “Student: no” with no Assistant line). That would explain the model thinking it still has to “answer” and calling the tool again.
- **Even when the frontend does send the qanda turn**, the intent model only sees “Assistant: Do you want harder questions?” in the prompt. It does **not** see that we already provided practice questions. So from the model’s point of view, the “previous answer” is just that one line — the **full** previous answer (the list of questions) is **not** in the thread we pass to the model.

So “the AI’s previous answer not added to the thread” can mean either:

- **A)** Frontend not sending the assistant qanda message in the next request (conversation missing that turn).
- **B)** Backend only putting the qanda **closing message** into the intent prompt, not a summary like “already delivered N questions,” so the model doesn’t see that the “generate questions” request was already fulfilled.

Planned fixes:

- **Verify frontend:** Ensure the client appends the full assistant message (including `type: "qanda"`, `data: { questions, message }`) to the conversation and sends it on the next message. If the frontend only keeps “content” and drops qanda messages, that’s the bug.
- **Improve thread for intent:** When building the prompt in `_build_conversation_prompt`, for qanda messages include a short summary so the model sees that we already answered, e.g. “Assistant: [Provided N practice question(s).] &lt;closing message&gt;” instead of only “Assistant: &lt;closing message&gt;”. That way the intent model sees that “generate questions” was already done and “no” is an answer to the follow-up, not a new request.

---

## 2. Why the AI returns a fixed “Do you want harder questions?” — guide behavior, not response

Today the closing message is effectively **fixed** in several places:

| Location | What it does |
|----------|----------------|
| [tutorx/schemas.py](tutorx/schemas.py) ~line 70 | Schema `message` description: “Always set to exactly: \"Do you want harder questions?\"" — **forces** the model to output that exact string. |
| [tutorx/services/ai.py](tutorx/services/ai.py) ~line 658 | Prompt: “Include a closing message asking if they want harder questions.” — **guides behavior** (good). |
| [tutorx/services/ai.py](tutorx/services/ai.py) ~line 674 | Fallback: `parsed.get("message", "Do you want harder questions?")` — **hardcodes** the string when missing. |
| [tutorx/services/handlers.py](tutorx/services/handlers.py) ~line 49 | Fallback: `result.get("message", "Do you want harder questions?")` — same **hardcode**. |

So we are both **guiding behavior** (prompt) and **dictating the exact response** (schema + fallbacks). The desired approach: **guide behavior, not the exact wording** — the AI should choose a natural, context-appropriate closing (e.g. “Want harder questions?” / “Need more practice?” / “Anything else?”).

Planned changes:

1. **Schema ([tutorx/schemas.py](tutorx/schemas.py))**
   - Change the `message` property description from “Always set to exactly: \"Do you want harder questions?\"" to a **behavioral** description, e.g. “A short, friendly closing message to the student (e.g. offering more or harder questions, or asking if they need anything else). One sentence.”
   - Do **not** require or suggest a single fixed string so the model can vary the wording.

2. **Prompt ([tutorx/services/ai.py](tutorx/services/ai.py) `generate_questions_for_lesson_chat`)**
   - Keep or slightly generalize the instruction, e.g. “Include a brief closing message (e.g. offering more or harder questions, or asking if they need anything else).” So we **guide behavior** (what kind of closing) without fixing the words.

3. **Fallbacks**
   - In [tutorx/services/ai.py](tutorx/services/ai.py) and [tutorx/services/handlers.py](tutorx/services/handlers.py), replace the hardcoded `"Do you want harder questions?"` fallback with something generic (e.g. “Want to try more questions?” or “Anything else I can help with?”) or leave empty and let the caller handle missing message. Prefer a short, neutral fallback so we don’t force one exact phrase.

Result: the AI still follows the **behavior** (close with an offer of more/harder questions or similar) but can respond **intelligently** with different wordings. No code changes in this file — plan only.

---

## Summary

| Issue | Cause | Planned fix |
|-------|--------|-------------|
| Previous answer not (fully) in thread | (A) Frontend might not send qanda in next request. (B) Backend only puts qanda’s `message` in the intent prompt, so the model doesn’t see “already delivered questions”. | (A) Verify frontend sends full conversation including qanda. (B) In `_build_conversation_prompt`, for qanda include a short summary (e.g. “[Provided N practice question(s).]” + closing message). |
| Fixed “Do you want harder questions?” | Schema forces exact string; fallbacks hardcode it. | Describe desired **behavior** in schema and prompt; let the AI choose wording; use a generic or minimal fallback. |

No implementation in this doc — plan only for review before making changes.
