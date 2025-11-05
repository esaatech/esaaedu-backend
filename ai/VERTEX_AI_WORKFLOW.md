# Vertex AI Base Workflow - Wireframe

## Core Flow: Initialization → Function Calling

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 1: INITIALIZATION                      │
└─────────────────────────────────────────────────────────────────┘

1. GeminiAgent.__init__()
   │
   ├─> Load config (GCP_PROJECT_ID, VERTEX_AI_LOCATION, GEMINI_MODEL)
   │
   ├─> _get_credentials()
   │   └─> Load service account JSON or use default credentials
   │
   └─> aiplatform.init(project, location, credentials)
       └─> Initialize Vertex AI SDK
           └─> Ready to use Vertex AI


┌─────────────────────────────────────────────────────────────────┐
│               PHASE 2: CHAT SESSION SETUP                       │
└─────────────────────────────────────────────────────────────────┘

2. start_chat_session()
   │
   ├─> Get function schema from schemas.py
   │   └─> get_function_calling_schema()
   │       └─> Returns: {name, description, parameters}
   │
   ├─> Create FunctionDeclaration
   │   └─> FunctionDeclaration(name="generate_course", ...)
   │
   ├─> Create Tool
   │   └─> Tool(function_declarations=[function_declaration])
   │
   ├─> Create GenerativeModel
   │   └─> GenerativeModel(
   │         model_name="gemini-2.0-flash-001",
   │         system_instruction="...",
   │         tools=[Tool(...)]
   │       )
   │
   ├─> Start ChatSession
   │   └─> chat = model.start_chat()
   │       └─> Returns: ChatSession object
   │
   └─> Return (chat, generation_config)
       └─> ChatSession ready with function calling enabled


┌─────────────────────────────────────────────────────────────────┐
│              PHASE 3: USER MESSAGE → AI RESPONSE               │
└─────────────────────────────────────────────────────────────────┘

3. User sends message: "create a course on java"
   │
   └─> chat.send_message("create a course on java", generation_config)
       │
       ├─> Vertex AI processes message
       │   ├─> Reads system_instruction
       │   ├─> Checks available tools (generate_course function)
       │   ├─> Reads function description
       │   └─> Decides: Call function or respond with text?
       │
       └─> Response object returned
           │
           ├─> CASE 1: Function Call Detected
           │   └─> response has function_call data
           │       └─> function_call.name = "generate_course"
           │       └─> function_call.args = {"user_request": "create a course on java"}
           │
           └─> CASE 2: Normal Text Response
               └─> response.text = "Hello! How can I help you?"


┌─────────────────────────────────────────────────────────────────┐
│              PHASE 4: FUNCTION CALL DETECTION                   │
└─────────────────────────────────────────────────────────────────┘

4. Check response for function call
   │
   ├─> Try: response.text
   │   └─> If fails → likely has function_call
   │
   ├─> Check: response.candidates[0].content.parts[0].function_call
   │   └─> If exists → function call detected
   │
   └─> Extract:
       ├─> function_name = function_call.name
       └─> function_args = function_call.args


┌─────────────────────────────────────────────────────────────────┐
│              PHASE 5: FUNCTION EXECUTION                        │
└─────────────────────────────────────────────────────────────────┘

5. Execute function call
   │
   ├─> If function_name == "generate_course"
   │   │
   │   ├─> Extract user_request from function_args
   │   │
   │   ├─> Call handle_course_generation(user_request)
   │   │   │
   │   │   ├─> Get course schema: get_course_generation_schema()
   │   │   │   └─> Returns: JSON schema for course structure
   │   │   │
   │   │   ├─> Call generate_structured_content()
   │   │   │   │
   │   │   │   ├─> Create new GenerativeModel (Level 2 AI)
   │   │   │   │   └─> No tools, just structured output
   │   │   │   │
   │   │   │   ├─> Generate content with schema instruction
   │   │   │   │   └─> "Generate course matching this schema: {...}"
   │   │   │   │
   │   │   │   └─> Parse JSON response
   │   │   │       └─> Returns: {title, description, category, ...}
   │   │   │
   │   │   └─> Return course_data
   │   │
   │   └─> Send course_data to frontend
   │       └─> JSON response with course information


┌─────────────────────────────────────────────────────────────────┐
│                    DATA FLOW DIAGRAM                            │
└─────────────────────────────────────────────────────────────────┘

User Input
    │
    ▼
chat.send_message(message)
    │
    ▼
Vertex AI Model
    ├─> Reads system_instruction
    ├─> Sees available tools (generate_course)
    ├─> Reads function description
    └─> Decides: Function call or text?
        │
        ├─► Function Call Path
        │   │
        │   ├─> Response: function_call object
        │   │   ├─> name: "generate_course"
        │   │   └─> args: {"user_request": "..."}
        │   │
        │   └─> Execute function
        │       └─> handle_course_generation()
        │           └─> Level 2 AI generates structured course
        │               └─> Return course_data
        │
        └─► Text Response Path
            │
            └─> Response: text string
                └─> Display to user


┌─────────────────────────────────────────────────────────────────┐
│                    KEY COMPONENTS                               │
└─────────────────────────────────────────────────────────────────┘

1. GenerativeModel
   └─> The AI model (gemini-2.0-flash-001)
       ├─> system_instruction: How AI should behave
       └─> tools: Functions AI can call

2. ChatSession
   └─> Manages conversation history
       └─> send_message() → Sends message, returns response

3. FunctionDeclaration
   └─> Defines a function AI can call
       ├─> name: "generate_course"
       ├─> description: When to call it
       └─> parameters: What it accepts

4. Tool
   └─> Wraps FunctionDeclaration
       └─> Passed to GenerativeModel constructor

5. Response Object
   ├─> response.text → Text response (if no function call)
   └─> response.candidates[0].content.parts[0].function_call
       └─> Function call data (if function was called)


┌─────────────────────────────────────────────────────────────────┐
│                    CODE LOCATIONS                               │
└─────────────────────────────────────────────────────────────────┘

Initialization:
  └─> gemini_agent.py:35-64 → GeminiAgent.__init__()

Chat Session Setup:
  ├─> gemini_agent.py:124-178 → start_chat_session()
  ├─> schemas.py:39-69 → get_function_calling_schema()
  └─> gemini_agent.py:147-158 → Create FunctionDeclaration & Tool

Message Sending:
  └─> consumers.py:353 → chat.send_message()

Function Detection:
  └─> consumers.py:380-442 → _detect_function_calls()

Function Execution:
  └─> consumers.py:444-509 → _handle_function_call()
      └─> gemini_agent.py:180-214 → handle_course_generation()


┌─────────────────────────────────────────────────────────────────┐
│                    DECISION POINTS                              │
└─────────────────────────────────────────────────────────────────┘

Decision 1: Does response have text?
    ├─> YES → Normal conversation
    └─> NO → Check for function_call

Decision 2: Does response have function_call?
    ├─> YES → Extract function_name and args
    └─> NO → Display text response

Decision 3: Which function was called?
    ├─> "generate_course" → Execute course generation
    └─> Other → Error (unknown function)

Decision 4: Function executed successfully?
    ├─> YES → Send course_data to frontend
    └─> NO → Send error message

