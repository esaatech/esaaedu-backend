# Function Calling Workflow - Wireframe Diagram
## gemini_agent.py - Complete Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PHASE 1: INITIALIZATION                              │
│                         (One-time setup)                                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. GeminiAgent.__init__()                                                 │
│    ├─> Load config (GCP_PROJECT_ID, VERTEX_AI_LOCATION, GEMINI_MODEL)      │
│    ├─> _get_credentials()                                                   │
│    │   ├─> Check GOOGLE_APPLICATION_CREDENTIALS env var                    │
│    │   ├─> Try .credentials/vertex-ai-service-account.json                 │
│    │   └─> Return credentials or None                                       │
│    └─> aiplatform.init(project, location, credentials)                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. start_chat_session(enable_function_calling=True)                         │
│    ├─> get_function_calling_schema()  [from schemas.py]                    │
│    │   └─> Returns:                                                          │
│    │       {                                                                │
│    │         "name": "generate_course",                                     │
│    │         "description": "Generate a structured course...",              │
│    │         "parameters": {...}                                            │
│    │       }                                                                │
│    ├─> FunctionDeclaration(name, description, parameters)                   │
│    ├─> Tool(function_declarations=[function_declaration])                  │
│    ├─> _get_model(system_instruction, tools=[Tool])                       │
│    │   └─> GenerativeModel(model_name, system_instruction, tools)         │
│    └─> model.start_chat()  → Returns ChatSession                            │
│        └─> ChatSession now has function available                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PHASE 2: CONVERSATION LOOP                            │
│                      (Repeated for each message)                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. User Input: "create a java course for me"                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. chat.send_message(user_input, generation_config, stream=False)          │
│    │                                                                         │
│    ├─> ChatSession automatically includes ALL previous messages             │
│    │   from chat.history (native history management)                        │
│    │                                                                         │
│    ├─> Vertex AI API receives:                                              │
│    │   [                                                                     │
│    │     {role: "user", content: "Hello"},                                 │
│    │     {role: "model", content: "Hi! How can I help?"},                   │
│    │     {role: "user", content: "create a java course"}  ← Current        │
│    │   ]                                                                     │
│    │                                                                         │
│    └─> Vertex AI processes with tools available                             │
│        └─> AI decides: "This user wants to generate a course"               │
│            └─> AI calls: generate_course function                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. Response Structure (from Vertex AI)                                      │
│    │                                                                         │
│    Response Object:                                                         │
│    {                                                                         │
│      candidates: [                                                           │
│        {                                                                    │
│          content: {                                                          │
│            role: "model",                                                    │
│            parts: [                                                          │
│              {                                                               │
│                function_call: {  ← NO TEXT, ONLY FUNCTION CALL              │
│                  name: "generate_course",                                   │
│                  args: {                                                     │
│                    "user_request": "create a java course",                  │
│                    "title": "Java Programming"                              │
│                  }                                                           │
│                }                                                             │
│              }                                                               │
│            ]                                                                 │
│          }                                                                   │
│        }                                                                    │
│      ]                                                                       │
│    }                                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ 6. Function Call Detection (interactive_chat)                                │
│    │                                                                         │
│    ├─> Try: response.text                                                   │
│    │   └─> ❌ ERROR: "Response has no text, contains function_call"         │
│    │                                                                         │
│    ├─> Check: response.candidates[].content.parts[].function_call          │
│    │   └─> ✅ Found: function_call.name = "generate_course"                │
│    │                                                                         │
│    └─> Extract:                                                              │
│        ├─> function_name = "generate_course"                               │
│        └─> function_args = {"user_request": "...", "title": "..."}         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ 7. Function Execution Handler                                               │
│    │                                                                         │
│    ├─> if function_name == "generate_course":                               │
│    │   │                                                                     │
│    │   ├─> Extract: course_request from function_args                       │
│    │   │                                                                     │
│    │   └─> service.handle_course_generation(course_request)                 │
│    │       │                                                                 │
│    │       ├─> get_course_generation_schema()  [from schemas.py]           │
│    │       │   └─> Returns JSON schema:                                       │
│    │       │       {                                                         │
│    │       │         "type": "object",                                       │
│    │       │         "properties": {                                         │
│    │       │           "title": {...},                                      │
│    │       │           "description": {...},                                │
│    │       │           "lessons": [...]                                     │
│    │       │         }                                                       │
│    │       │       }                                                         │
│    │       │                                                                 │
│    │       ├─> generate_structured_content()                                 │
│    │       │   ├─> Build prompt with schema instructions                    │
│    │       │   ├─> Call model.generate_content()                           │
│    │       │   ├─> Parse JSON response                                      │
│    │       │   └─> Return structured dict                                   │
│    │       │                                                                 │
│    │       └─> Return: course_data (Dict)                                    │
│    │           {                                                             │
│    │             "title": "Java Programming Fundamentals",                 │
│    │             "description": "...",                                      │
│    │             "lessons": [...]                                           │
│    │           }                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ 8. Function Response Handling                                               │
│    │                                                                         │
│    ├─> Display structured course_data to user                               │
│    │                                                                         │
│    ├─> Create summary message:                                              │
│    │   "I've successfully generated a course on 'Java...'                   │
│    │    with 10 lessons..."                                                 │
│    │                                                                         │
│    └─> chat.send_message(course_summary, stream=True)                        │
│        ├─> ChatSession adds summary to history                              │
│        └─> AI responds with confirmation/next steps                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ 9. Final Response to User                                                   │
│    │                                                                         │
│    Stream response chunks:                                                   │
│    "I've successfully generated a comprehensive course on                  │
│     'Java Programming Fundamentals'..."                                      │
│    │                                                                         │
│    └─> Display to user                                                       │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                        KEY COMPONENTS                                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ Level 1: Main Chat AI (Intent Detection)                                     │
│ ├─> ChatSession with tools=[Tool(function_declarations=[...])]             │
│ ├─> Interprets user messages                                                │
│ └─> Decides when to call functions                                          │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ Level 2: Course Generation AI (Structured Output)                           │
│ ├─> handle_course_generation()                                               │
│ ├─> Uses generate_structured_content()                                      │
│ ├─> Uses get_course_generation_schema()                                     │
│ └─> Returns structured JSON matching schema                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ Schema Files (Separated Concerns)                                           │
│ ├─> schemas.py                                                              │
│ │   ├─> get_function_calling_schema()  → Function declaration               │
│ │   └─> get_course_generation_schema() → Output structure                   │
│ └─> Both can be modified independently                                      │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                        DATA FLOW DIAGRAM                                    │
└─────────────────────────────────────────────────────────────────────────────┘

User Input: "create a java course"
    ↓
[ChatSession.send_message()]
    ↓
Vertex AI API (with tools registered)
    ↓
    ├─> AI Analysis: "This is a course generation request"
    └─> AI Decision: Call generate_course()
        ↓
Response: {function_call: {name: "generate_course", args: {...}}}
    ↓
[Function Call Detection]
    ↓
service.handle_course_generation()
    ↓
    ├─> get_course_generation_schema()  [schemas.py]
    ├─> generate_structured_content()
    │   └─> Vertex AI API call with schema
    └─> Returns: {title, description, lessons, ...}
        ↓
Display structured data + Send summary back to chat
    ↓
ChatSession continues conversation


┌─────────────────────────────────────────────────────────────────────────────┐
│                        MESSAGE SEQUENCE                                      │
└─────────────────────────────────────────────────────────────────────────────┘

1. User → "create a java course"
   ↓
2. ChatSession → [Includes history] → Vertex AI
   ↓
3. Vertex AI → Analyzes → Decides to call generate_course()
   ↓
4. Response → {function_call: {...}} (NO TEXT)
   ↓
5. Code → Detects function_call → Extracts function_name & args
   ↓
6. Code → Calls handle_course_generation("create a java course")
   ↓
7. Level 2 AI → Generates structured course data
   ↓
8. Code → Displays course_data + Sends summary to ChatSession
   ↓
9. ChatSession → [Includes function result] → Vertex AI
   ↓
10. Vertex AI → Responds with confirmation message
    ↓
11. User → Sees structured course data + AI confirmation


┌─────────────────────────────────────────────────────────────────────────────┐
│                        VISUAL FLOWCHART                                      │
└─────────────────────────────────────────────────────────────────────────────┘

                    START
                     │
                     ▼
        ┌────────────────────────┐
        │  Initialize Service    │
        │  - Load credentials     │
        │  - Init Vertex AI       │
        └────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  start_chat_session()  │
        │  - Get function schema │
        │  - Create Tool          │
        │  - Create Model         │
        │  - Start ChatSession    │
        └────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  User sends message    │
        │  "create java course"   │
        └────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  chat.send_message()    │
        │  - Includes history     │
        │  - Sends to Vertex AI   │
        └────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  Vertex AI Processes   │
        │  - Sees tools available │
        │  - Analyzes intent     │
        │  - Decides: Call func? │
        └────────────────────────┘
                     │
                     ├─────────────────┐
                     │                 │
                     ▼                 ▼
        ┌──────────────────┐  ┌──────────────────┐
        │  Normal Response │  │ Function Call    │
        │  (has text)       │  │ (no text)        │
        └──────────────────┘  └──────────────────┘
                     │                 │
                     │                 ▼
                     │     ┌──────────────────────┐
                     │     │ Detect function_call  │
                     │     │ Extract name & args   │
                     │     └──────────────────────┘
                     │                 │
                     │                 ▼
                     │     ┌──────────────────────┐
                     │     │ if name ==            │
                     │     │ "generate_course":    │
                     │     └──────────────────────┘
                     │                 │
                     │                 ▼
                     │     ┌──────────────────────┐
                     │     │ handle_course_        │
                     │     │ generation()          │
                     │     │  [Level 2 AI]         │
                     │     └──────────────────────┘
                     │                 │
                     │                 ▼
                     │     ┌──────────────────────┐
                     │     │ get_course_           │
                     │     │ generation_schema()   │
                     │     └──────────────────────┘
                     │                 │
                     │                 ▼
                     │     ┌──────────────────────┐
                     │     │ generate_structured_ │
                     │     │ content()            │
                     │     │ - Uses schema        │
                     │     │ - Returns JSON       │
                     │     └──────────────────────┘
                     │                 │
                     │                 ▼
                     │     ┌──────────────────────┐
                     │     │ course_data (Dict)   │
                     │     │ {title, lessons...}  │
                     │     └──────────────────────┘
                     │                 │
                     │                 ▼
                     │     ┌──────────────────────┐
                     │     │ Send summary back     │
                     │     │ to ChatSession        │
                     │     └──────────────────────┘
                     │                 │
                     └─────────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  Stream Response  │
                    │  to User          │
                    └──────────────────┘
                             │
                             ▼
                           END


┌─────────────────────────────────────────────────────────────────────────────┐
│                        CODE LOCATIONS                                        │
└─────────────────────────────────────────────────────────────────────────────┘

Initialization:
  ├─> gemini_agent.py:21-50    → GeminiAgent.__init__()
  └─> gemini_agent.py:121-170  → start_chat_session()

Schema Loading:
  ├─> schemas.py:64-94     → get_function_calling_schema()
  └─> schemas.py:6-61      → get_course_generation_schema()

Function Registration:
  └─> gemini_agent.py:140-154   → Create Tool with FunctionDeclaration

Message Sending:
  └─> gemini_agent.py:438-442  → chat.send_message()

Function Call Detection:
  └─> gemini_agent.py:444-511  → Check response for function_call

Function Execution:
  ├─> gemini_agent.py:534      → if function_name == "generate_course"
  └─> gemini_agent.py:176-209  → handle_course_generation()

Structured Generation:
  └─> gemini_agent.py:312-359 → generate_structured_content()

Response Handling:
  └─> gemini_agent.py:547-579 → Display data + Send summary


┌─────────────────────────────────────────────────────────────────────────────┐
│                        KEY DECISION POINTS                                   │
└─────────────────────────────────────────────────────────────────────────────┘

Decision 1: Does response have text?
    ├─> YES → Normal conversation → Display text
    └─> NO → Check for function_call

Decision 2: Is function_call valid?
    ├─> YES → Extract function_name & args
    └─> NO → Error handling

Decision 3: Which function was called?
    ├─> "generate_course" → Call handle_course_generation()
    └─> Other → Error (unknown function)

Decision 4: Function response format?
    ├─> Try Part/Content objects → May fail
    └─> Fallback → Send summary text message

