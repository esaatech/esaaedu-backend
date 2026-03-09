# Lesson Chat: Tools, Schemas, Functions, and Handlers

This tutorial explains how the lesson chat uses **tools**, **schemas**, **functions**, and **handlers** so the AI can infer what the student wants and we can run the right code. All of this is in the context of our TutorX lesson chat (POST `/api/tutorx/lessons/<lesson_id>/chat/`).

---

## 1. What each term means (in our code)

### Tool

A **tool** is something the model is *allowed to call* when it thinks the user’s message matches that action. We don’t execute the tool ourselves at this step; we only *declare* it so the model can choose it and return a **function call** (name + arguments).

- **Where:** Declared in **`tutorx/schemas.py`** as **tool schemas** (Vertex AI format).
- **What we use:** `get_lesson_chat_tool_schemas_vertex()` returns a list of tools, each with:
  - `name` – e.g. `"explain_better"`, `"generate_questions"`, `"draw_explainer_image"`
  - `description` – when the model should pick this tool
  - `parameters` – JSON Schema of the arguments the model should fill (e.g. `phrase_or_concept`, `user_message`)

So: **tools = the list of “actions” we offer the model for intent.**

---

### Function (and function call)

A **function** in this context is one of those tools from the model’s point of view. When the model decides to use a tool, it returns a **function call**: a function **name** and **arguments** (e.g. `explain_better(phrase_or_concept="this phrase", user_message="I don't understand this phrase")`).

- **Where:** The model returns it from **`GeminiService.generate_with_tools()`** in **`ai/gemini_service.py`**. We parse the response and get something like `{"function_call": {"name": "explain_better", "args": {"phrase_or_concept": "this phrase", "user_message": "..."}}}`.
- **Flow:** We pass the **tool schemas** into `generate_with_tools()`. The model reads the user message (and lesson context) and either returns a **function_call** (name + args) or plain **text**.

So: **function = one of the tools; function call = the model’s choice of which tool and with what arguments.**

---

### Schema

We use **schemas** in two places:

1. **Tool schema (for intent)**  
   Describes *what* the model can call and *what arguments* it must send. Same as the “tool” definition above: **`get_lesson_chat_tool_schemas_vertex()`** in **`tutorx/schemas.py`**. Each tool has `name`, `description`, and `parameters` (JSON Schema).

2. **Response schema (for structured output)**  
   When a **handler** calls the AI to produce a structured reply (e.g. Q&A list or image prompt), we pass a **response schema** so the model returns valid JSON matching that shape. Examples:
   - **`get_student_generate_questions_schema()`** – for “generate questions” (list of questions + message).
   - **`get_draw_explainer_image_schema()`** – for “draw explainer image” (image_description, image_prompt).

So: **schema = either the “contract” for the model’s function arguments (tool schema) or the “contract” for the handler’s AI response (response schema).**

---

### Handler

A **handler** is the backend function we run when the model returns a **function_call** for that tool. It takes the **args** from the model (and lesson context, etc.), calls our AI or logic, and returns the result we send back to the client (text or structured data).

- **Where:** **`tutorx/services/handlers.py`**.
- **Functions:**
  - **`handle_explain_better(lesson_context, phrase_or_concept, user_message)`** → plain text.
  - **`handle_generate_questions(lesson_context, user_message)`** → `{ "questions", "message" }` (qanda).
  - **`handle_draw_explainer_image(lesson_context, concept, user_message)`** → `{ "image_description", "image_prompt" }`.

Dispatch (which handler to call for which function name) happens in **`tutorx/services/lesson_chat.py`** in **`run_lesson_chat()`**.

So: **handler = our code that runs for a given tool/function and produces the actual response.**

---

## 2. How they work together

```
User message
    → We send it (with lesson context) to the model WITH the list of TOOL SCHEMAS.
    → Model returns either a FUNCTION CALL (name + args) or plain text.
    → If function call: we look up the HANDLER for that name and call it with the args (and lesson context).
    → Handler may use a RESPONSE SCHEMA when it calls the AI again (e.g. for generate_questions, draw_explainer_image).
    → We return the handler’s result to the client (with response_type: text, qanda, or explainer_image).
```

- **Tool schema** = “what the model can call” (intent step).
- **Function / function call** = “model’s choice” (name + args).
- **Handler** = “our code for that choice” (does the work).
- **Response schema** = “shape of the handler’s AI output” when we need structured JSON.

---

## 3. Where each lives in the codebase

| Concept            | Where it lives | What it does |
|--------------------|----------------|--------------|
| Tool (declaration) | `tutorx/schemas.py` → `get_lesson_chat_tool_schemas_vertex()` | List of tools (name, description, parameters) for intent |
| Function call      | Returned by `ai/gemini_service.py` → `generate_with_tools()` | Model returns `{ "name", "args" }` for one tool |
| Response schema   | `tutorx/schemas.py` → e.g. `get_student_generate_questions_schema()`, `get_draw_explainer_image_schema()` | Tells the AI which JSON shape to return inside a handler |
| Handler            | `tutorx/services/handlers.py` → `handle_explain_better`, `handle_generate_questions`, `handle_draw_explainer_image` | Runs when we get that function call; returns text or data |
| Dispatch           | `tutorx/services/lesson_chat.py` → `run_lesson_chat()` | Calls `infer_intent()`, then the right handler by name |

---

## 4. Example: “I don’t understand this phrase”

End-to-end flow for one message.

### Step 1: Request

Client sends:

```http
POST /api/tutorx/lessons/<lesson_id>/chat/
Content-Type: application/json

{
  "message": "I don't understand this phrase",
  "conversation": []
}
```

### Step 2: Load context and infer intent

- **View** (`tutorx/views.py` → `LessonChatView`) gets `lesson_context` from **`get_lesson_context(lesson_id)`** (cached).
- It calls **`run_lesson_chat(lesson_context, message, conversation)`** in **`tutorx/services/lesson_chat.py`**.

### Step 3: Intent = tool schemas + one model call

- **`run_lesson_chat()`** calls **`infer_intent(lesson_context, user_message, conversation)`**.
- **`infer_intent()`**:
  - Builds a system prompt that includes the lesson content and instructions (“call one of these tools or respond with text”).
  - Gets **tool schemas** from **`get_lesson_chat_tool_schemas_vertex()`** (explain_better, generate_questions, draw_explainer_image).
  - Calls **`GeminiService.generate_with_tools(system_instruction, prompt, tool_schemas)`** in **`ai/gemini_service.py`**.

The model sees the user message and the tool list. It decides this is “explain something more simply” and returns a **function call**, for example:

```json
{
  "function_call": {
    "name": "explain_better",
    "args": {
      "phrase_or_concept": "this phrase",
      "user_message": "I don't understand this phrase"
    }
  }
}
```

So: **tools** = what we gave the model; **function call** = this JSON.

### Step 4: Dispatch to the handler

- **`run_lesson_chat()`** sees `"function_call"` and `name == "explain_better"`.
- It takes `args` and calls the **handler** for that name:

```python
from .handlers import handle_explain_better
phrase = args.get("phrase_or_concept") or user_message   # "this phrase"
text = handle_explain_better(
    lesson_context=lesson_context,
    phrase_or_concept=phrase,
    user_message=user_msg,
)
```

### Step 5: Handler runs (no response schema here)

- **`handle_explain_better()`** in **`tutorx/services/handlers.py`** calls **`TutorXAIService.explain_for_lesson_chat()`** in **`tutorx/services/ai.py`**.
- That method uses the **explain_more** system instruction and the lesson content + phrase to generate plain text. No **response schema** is used here because the answer is free-form text.

### Step 6: Response to client

- **`run_lesson_chat()`** builds:
  - `response_type = "text"`
  - `content = text` (the explanation)
  - `assistant_msg = { "role": "assistant", "type": "text", "content": text }`
- The view returns:

```json
{
  "response_type": "text",
  "content": "Here’s a simpler way to think about it: ...",
  "conversation": [
    { "role": "user", "content": "I don't understand this phrase" },
    { "role": "assistant", "type": "text", "content": "Here’s a simpler way to think about it: ..." }
  ]
}
```

So for this example: **tool** = explain_better in the schema, **function call** = model’s choice with args, **handler** = `handle_explain_better` (which uses AI with no response schema), **response** = text.

---

## 5. Example: “Generate questions” (uses a response schema)

When the user says something like “Give me some practice questions”:

1. **Intent:** Same as above. Model returns `function_call` with `name: "generate_questions"` and `args: { "user_message": "..." }`.
2. **Dispatch:** **`run_lesson_chat()`** calls **`handle_generate_questions(lesson_context, user_message)`** from **`handlers.py`**.
3. **Handler:** **`handle_generate_questions()`** calls **`TutorXAIService.generate_questions_for_lesson_chat()`**. That method calls the AI with a **response schema**: **`get_student_generate_questions_schema()`** from **`tutorx/schemas.py`**, so the AI returns JSON like `{ "questions": [...], "message": "Do you want harder questions?" }`.
4. **Response:** We return `response_type: "qanda"` and `data: { "questions", "message" }` so the frontend can render the Q&A block.

Here the **response schema** is what forces the handler’s AI output into the structured shape we need for **qanda**.

---

## 6. Adding a new intent (checklist)

To add a new “action” (e.g. “summarize this lesson”):

1. **Tool schema** – In **`tutorx/schemas.py`**, add a new entry in **`get_lesson_chat_tool_schemas_vertex()`** (and optionally in **`get_lesson_chat_tool_declarations()`**) with `name`, `description`, and `parameters`.
2. **Handler** – In **`tutorx/services/handlers.py`**, add e.g. **`handle_summarize_lesson(lesson_context, user_message)`** that calls the AI and returns text or a dict.
3. **Response schema (optional)** – If the handler needs structured JSON from the AI, add a schema in **`tutorx/schemas.py`** (e.g. `get_summarize_lesson_schema()`) and pass it into the AI call inside the handler.
4. **Dispatch** – In **`tutorx/services/lesson_chat.py`** inside **`run_lesson_chat()`**, add a branch: when `name == "summarize_lesson"`, call your new handler and return the right `response_type` and payload.

That’s the full loop: **tool (schema) → function call (model) → handler (our code) → optional response schema (inside handler) → response to client.**
