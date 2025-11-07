"""
GeminiAgent - AI agent for Google Vertex AI (Gemini) with function calling capabilities
"""
import logging
import json
import os
import time
from typing import Dict, List, Optional, Any, AsyncGenerator, Tuple
from google.cloud import aiplatform
from google.oauth2 import service_account
from vertexai.generative_models import GenerativeModel, ChatSession, Tool, FunctionDeclaration, Part
from google.api_core import exceptions as google_exceptions
from decouple import config

# Handle imports for both script and module usage
try:
    from .schemas import (
        get_function_calling_schema, 
        get_course_generation_schema,
        get_course_introduction_schema,
        get_lesson_generation_schema,
        get_assignment_generation_schema,
        get_quiz_generation_schema
    )
except ImportError:
    # If running as script, add parent directory to path and import
    import sys
    import pathlib
    # Add ai directory to path
    current_dir = pathlib.Path(__file__).parent
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    from schemas import (
        get_function_calling_schema, 
        get_course_generation_schema,
        get_course_introduction_schema,
        get_lesson_generation_schema,
        get_assignment_generation_schema,
        get_quiz_generation_schema
    )

logger = logging.getLogger(__name__)


class GeminiAgent:
    """
    AI agent for interacting with Google Vertex AI Gemini models with AI-driven function calling.
    This agent can interpret user messages and automatically decide when to call specialized functions.
    """
    
    def __init__(self):
        """Initialize Vertex AI client"""
        self.project_id = config('GCP_PROJECT_ID', default=None)
        self.location = config('VERTEX_AI_LOCATION', default='us-central1')
        # Model name should be just the model identifier, not the full path
        # Available models: gemini-2.5-pro, gemini-2.5-flash, gemini-2.0-flash-001, gemini-2.0-flash-lite-001
        # Using gemini-2.0-flash-001 as default (fast and cost-effective)
        self.model_name = config('GEMINI_MODEL', default='gemini-2.0-flash-001')
        
        if not self.project_id:
            logger.warning("GCP_PROJECT_ID not set, Vertex AI may not work correctly")
        
        # Get credentials
        credentials = self._get_credentials()
        
        # Initialize Vertex AI
        if self.project_id:
            try:
                if credentials:
                    aiplatform.init(
                        project=self.project_id,
                        location=self.location,
                        credentials=credentials
                    )
                    logger.info(f"Vertex AI initialized for project: {self.project_id}, location: {self.location} (with service account)")
                else:
                    aiplatform.init(project=self.project_id, location=self.location)
                    logger.info(f"Vertex AI initialized for project: {self.project_id}, location: {self.location} (using default credentials)")
            except Exception as e:
                logger.error(f"Failed to initialize Vertex AI: {e}")
    
    def _get_credentials(self):
        """Get service account credentials if available"""
        # Check for explicit credentials file path
        creds_path = config('GOOGLE_APPLICATION_CREDENTIALS', default=None)
        
        # If not set, try default location for our service account
        if not creds_path:
            # Get project root: ai/gemini_agent.py -> ai/ (1 level) -> project root (2 levels)
            # Or use BASE_DIR from Django settings if available
            try:
                from django.conf import settings
                base_dir = settings.BASE_DIR
            except:
                # Fallback: calculate from current file location
                # ai/gemini_agent.py -> go up 2 levels to project root
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            default_path = os.path.join(base_dir, '.credentials', 'vertex-ai-service-account.json')
            if os.path.exists(default_path):
                creds_path = default_path
                logger.info(f"Found Vertex AI credentials at: {creds_path}")
        
        if creds_path and os.path.exists(creds_path):
            try:
                credentials = service_account.Credentials.from_service_account_file(creds_path)
                logger.info(f"Successfully loaded Vertex AI credentials from: {creds_path}")
                return credentials
            except Exception as e:
                logger.error(f"Failed to load credentials from {creds_path}: {e}", exc_info=True)
        else:
            if creds_path:
                logger.warning(f"Credentials file not found at: {creds_path}")
        
        # Return None to use default credentials (for Cloud Run)
        return None
    
    def _get_model(
        self, 
        system_instruction: Optional[str] = None,
        tools: Optional[List[Tool]] = None
    ) -> GenerativeModel:
        """
        Get the configured Gemini model
        
        Args:
            system_instruction: Optional system instruction to include in the model
            tools: Optional list of tools for function calling
        """
        model_kwargs = {}
        if system_instruction:
            model_kwargs["system_instruction"] = system_instruction
        if tools:
            model_kwargs["tools"] = tools
        
        return GenerativeModel(self.model_name, **model_kwargs)
    
    def start_chat_session(
        self,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        enable_function_calling: bool = True,
        function_schemas: Optional[List[dict]] = None,
    ) -> Tuple[ChatSession, dict]:
        """
        Start a new chat session with conversation history management and optional function calling
        
        Args:
            system_instruction: Optional system instruction for the chat
            temperature: Creativity level (0.0-1.0)
            enable_function_calling: Whether to enable AI-driven function calling
            function_schemas: Optional list of function schemas (if None, uses default from schemas.py)
            
        Returns:
            Tuple of (ChatSession object, generation_config dict)
            ChatSession manages conversation history automatically
        """
        try:
            # Prepare tools for function calling if enabled
            tools = None
            if enable_function_calling:
                # Use provided function schemas or get default
                if function_schemas is None:
                    function_schemas = get_function_calling_schema()
                
                # Create FunctionDeclarations for all functions
                function_declarations = []
                for function_schema in function_schemas:
                    function_declaration = FunctionDeclaration(
                        name=function_schema["name"],
                        description=function_schema["description"],
                        parameters=function_schema["parameters"]
                    )
                    function_declarations.append(function_declaration)
                
                # Create Tool with all function declarations
                tools = [Tool(function_declarations=function_declarations)]
            
            # Create model with system instruction and tools if provided
            # Tools must be passed when creating the model, not when starting chat
            model = self._get_model(
                system_instruction=system_instruction,
                tools=tools
            )
            
            # Start a chat session (automatically manages conversation history)
            # Note: generation_config is passed to send_message(), not start_chat()
            chat = model.start_chat()
            
            # Store generation config to pass to send_message() calls
            generation_config = {"temperature": temperature}
            
            return chat, generation_config
            
        except Exception as e:
            logger.error(f"Error starting chat session: {e}")
            raise
    
    async def handle_course_generation(
        self,
        user_request: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Handle course generation with structured output
        This is the Level 2 AI that generates structured course data
        
        Args:
            user_request: User's course generation request
            system_instruction: Optional system instruction for course generation
            temperature: Creativity level
            
        Returns:
            Dictionary matching the course generation schema
        """
        try:
            # Get the structured output schema
            course_schema = get_course_generation_schema()
            
            # Use structured content generation with the schema
            structured_response = await self.generate_structured_content(
                prompt=user_request,
                output_schema=course_schema,
                system_instruction=system_instruction,
                temperature=temperature,
            )
            
            return structured_response
            
        except Exception as e:
            logger.error(f"Error in course generation: {e}")
            raise
    
    async def handle_course_introduction_generation(
        self,
        course_title: str,
        course_description: str,
        user_request: str,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Handle course introduction generation with structured output
        This is the Level 2 AI that generates structured course introduction data
        
        Args:
            course_title: Title of the course
            course_description: Description of the course
            user_request: User's request for introduction generation
            temperature: Creativity level
            
        Returns:
            Dictionary matching the course introduction schema
        """
        try:
            # Get the structured output schema
            introduction_schema = get_course_introduction_schema()
            
            # Create prompt with course context
            prompt = f"""Course Title: {course_title}
Course Description: {course_description}

User Request: {user_request}

Generate comprehensive course introduction details including overview, learning objectives, prerequisites, duration, sessions per week, total projects, and value propositions."""
            
            # System instruction for course introduction generation
            system_instruction = """You are an expert course creator. Generate comprehensive course introduction details that are engaging, clear, and informative. 
            Create detailed learning objectives, identify prerequisites, suggest appropriate duration and session frequency, estimate project count, and highlight value propositions."""
            
            # Use structured content generation with the schema
            structured_response = await self.generate_structured_content(
                prompt=prompt,
                output_schema=introduction_schema,
                system_instruction=system_instruction,
                temperature=temperature,
            )
            
            return structured_response
            
        except Exception as e:
            logger.error(f"Error in course introduction generation: {e}")
            raise
    
    async def handle_lesson_generation(
        self,
        course_title: str = "",
        course_description: str = "",
        duration_weeks: Optional[int] = None,
        sessions_per_week: Optional[int] = None,
        user_request: str = "",
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Handle lesson generation with structured output
        This is the Level 2 AI that generates multiple lessons for an entire course
        Lessons follow a scaffolding/cumulative organization
        
        Args:
            course_title: Title of the course (optional - can use conversation context)
            course_description: Description of the course (optional - can use conversation context)
            duration_weeks: Number of weeks the course runs (optional)
            sessions_per_week: Number of sessions per week (optional)
            user_request: User's request for lesson generation
            temperature: Creativity level
            
        Returns:
            Dictionary with 'lessons' array matching the lesson generation schema
        """
        try:
            # Get the structured output schema
            lesson_schema = get_lesson_generation_schema()
            
            # Build prompt with available information
            prompt_parts = []
            
            if course_title:
                prompt_parts.append(f"Course Title: {course_title}")
            if course_description:
                prompt_parts.append(f"Course Description: {course_description}")
            if duration_weeks:
                prompt_parts.append(f"Course Duration: {duration_weeks} weeks")
            if sessions_per_week:
                prompt_parts.append(f"Sessions per Week: {sessions_per_week}")
            
            if user_request:
                prompt_parts.append(f"\nUser Request: {user_request}")
            
            # Calculate total lessons if duration and sessions are provided
            total_lessons = None
            if duration_weeks and sessions_per_week:
                total_lessons = duration_weeks * sessions_per_week
                prompt_parts.append(f"\nTotal Lessons Needed: {total_lessons} lessons ({duration_weeks} weeks × {sessions_per_week} sessions/week)")
            
            prompt = "\n".join(prompt_parts) if prompt_parts else user_request
            
            # Add instruction for lesson generation
            prompt += """

Generate lesson outlines (titles and descriptions) for the entire course. The lessons should:
1. Follow a scaffolding/cumulative organization - each lesson builds on previous ones
2. Progress from basic concepts to more advanced topics
3. Be organized in a logical learning sequence
4. Cover the full scope of the course content"""
            
            if total_lessons:
                prompt += f"\n5. Generate exactly {total_lessons} lessons to match the course duration"
            else:
                prompt += "\n5. Generate an appropriate number of lessons based on the course scope"
            
            # System instruction for lesson generation
            system_instruction = """You are an expert lesson creator and curriculum designer. Generate comprehensive lesson outlines for entire courses that follow educational scaffolding principles.

Key principles:
- Lessons should be cumulative - each lesson builds on knowledge from previous lessons
- Start with foundational concepts and progressively introduce more complex topics
- Ensure logical flow and sequencing
- Each lesson should have a clear, descriptive title and a detailed description
- Lessons should be organized in order (1, 2, 3, etc.)
- Consider the total number of lessons needed based on course duration and sessions per week

Create engaging, clear, and informative lesson outlines that help students understand what they will learn in each lesson and how lessons connect to form a complete learning journey."""
            
            # Use structured content generation with the schema
            structured_response = await self.generate_structured_content(
                prompt=prompt,
                output_schema=lesson_schema,
                system_instruction=system_instruction,
                temperature=temperature,
            )
            
            return structured_response
            
        except Exception as e:
            logger.error(f"Error in lesson generation: {e}")
            raise
    
    async def handle_assignment_generation(
        self,
        user_request: str,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Handle assignment generation with structured output
        This is the Level 2 AI that generates structured assignment data with questions
        
        Args:
            user_request: User's request for assignment generation (includes material content)
            temperature: Creativity level
            
        Returns:
            Dictionary matching the assignment generation schema
        """
        try:
            # Get the structured output schema
            assignment_schema = get_assignment_generation_schema()
            
            # System instruction for assignment generation
            system_instruction = """You are an expert assignment creator. Based on the provided material content, create assignment questions. 
            Use question types: essay and fill_blank. 
            
            For fill_blank questions:
            - Identify key concepts, terms, or important information from the material
            - Create fill-in-the-blank questions that test understanding
            - Provide correct answers for each blank
            
            For essay questions:
            - Create thought-provoking prompts that require students to analyze and synthesize the material
            - Include a rubric or grading criteria if helpful
            
            For short_answer questions:
            - Create questions that require brief but specific answers
            - Test comprehension of key concepts
            
            Generate a comprehensive assignment with multiple questions that effectively assess student understanding of the material."""
            
            # Use structured content generation with the schema
            structured_response = await self.generate_structured_content(
                prompt=user_request,
                output_schema=assignment_schema,
                system_instruction=system_instruction,
                temperature=temperature,
            )
            
            return structured_response
            
        except Exception as e:
            logger.error(f"Error in assignment generation: {e}")
            raise
    
    async def handle_quiz_generation(
        self,
        user_request: str,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Handle quiz generation with structured output
        This is the Level 2 AI that generates structured quiz data with questions
        
        Args:
            user_request: User's request for quiz generation (includes material content)
            temperature: Creativity level
            
        Returns:
            Dictionary matching the quiz generation schema
        """
        try:
            # Get the structured output schema
            quiz_schema = get_quiz_generation_schema()
            
            # System instruction for quiz generation
            system_instruction = """You are an expert quiz creator. Based on the provided material content, create quiz questions. 
            Use question types: multiple_choice and true_false. 
            
            For multiple_choice questions:
            - Create 4 options with one correct answer
            - Make distractors plausible but clearly incorrect
            - Test understanding of key concepts from the material
            
            For true_false questions:
            - Create statements that test understanding of key concepts
            - Ensure statements are clearly true or false based on the material
            - Avoid ambiguous statements
            
            Generate a comprehensive quiz with multiple questions that effectively assess student understanding of the material."""
            
            # Use structured content generation with the schema
            structured_response = await self.generate_structured_content(
                prompt=user_request,
                output_schema=quiz_schema,
                system_instruction=system_instruction,
                temperature=temperature,
            )
            
            return structured_response
            
        except Exception as e:
            logger.error(f"Error in quiz generation: {e}")
            raise
    
    def process_function_call(
        self,
        function_name: str,
        function_args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process function calls made by the AI
        Routes to appropriate handler based on function name
        
        Args:
            function_name: Name of the function AI wants to call
            function_args: Arguments passed by the AI
            
        Returns:
            Result of function execution as dict
        """
        try:
            if function_name == "generate_course":
                # Extract user request from function args
                # The AI might pass the request in different ways
                user_request = function_args.get("user_request") or function_args.get("request") or str(function_args)
                
                # Call the course generation handler
                # Note: This is sync, but the actual generation is async
                # We'll need to handle this properly in the chat loop
                return {
                    "function_name": function_name,
                    "user_request": user_request,
                    "function_args": function_args
                }
            else:
                raise ValueError(f"Unknown function: {function_name}")
                
        except Exception as e:
            logger.error(f"Error processing function call: {e}")
            raise
    
    async def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate content from Gemini model (non-streaming)
        
        Args:
            prompt: User prompt/request
            system_instruction: System-level instructions for the model
            temperature: Creativity level (0.0-1.0)
            max_tokens: Maximum tokens in response
            
        Returns:
            Generated text response
        """
        try:
            # Create model with system instruction if provided
            model = self._get_model(system_instruction=system_instruction)
            
            generation_config = {
                "temperature": temperature,
            }
            if max_tokens:
                generation_config["max_output_tokens"] = max_tokens
            
            # Generate content (system instruction is already in the model)
            response = model.generate_content(
                prompt,
                generation_config=generation_config,
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            raise
    
    async def generate_content_stream(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """
        Generate content with streaming (for real-time updates)
        
        Args:
            prompt: User prompt/request
            system_instruction: System-level instructions
            temperature: Creativity level
            
        Yields:
            Chunks of generated text
        """
        try:
            # Create model with system instruction if provided
            model = self._get_model(system_instruction=system_instruction)
            
            generation_config = {
                "temperature": temperature,
            }
            
            # Generate content with streaming (system instruction is already in the model)
            responses = model.generate_content(
                prompt,
                generation_config=generation_config,
                stream=True,
            )
            
            for chunk in responses:
                if chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            logger.error(f"Error streaming content: {e}")
            raise
    
    async def generate_structured_content(
        self,
        prompt: str,
        output_schema: Dict[str, Any],
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Generate structured content matching a JSON schema
        
        Args:
            prompt: User prompt
            output_schema: Expected JSON schema for response
            system_instruction: System instructions
            temperature: Creativity level
            
        Returns:
            Dictionary matching the output schema
        """
        try:
            # Add schema instruction to prompt
            schema_prompt = f"""{prompt}

Output your response as valid JSON matching this schema:
{output_schema}

Return ONLY valid JSON, no additional text or markdown formatting."""

            response_text = await self.generate_content(
                schema_prompt,
                system_instruction=system_instruction,
                temperature=temperature,
            )
            
            # Parse JSON response
            import json
            # Remove markdown code blocks if present
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            return json.loads(response_text)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text: {response_text[:500]}")
            raise ValueError(f"Invalid JSON response from AI: {e}")
        except Exception as e:
            logger.error(f"Error generating structured content: {e}")
            raise


# ============================================================================
# INTERACTIVE CHAT - Run this file directly to chat with Gemini Agent
# Usage: python ai/gemini_agent.py
# ============================================================================
async def interactive_chat():
    """Interactive chat with Gemini Agent using ChatSession API"""
    print("\n" + "="*70)
    print("GEMINI AGENT INTERACTIVE CHAT (Using ChatSession API)")
    print("="*70)
    print("Type your messages below. Type 'quit', 'exit', or Ctrl+C to end the chat.\n")
    
    try:
        # Initialize agent
        print("Initializing GeminiAgent...")
        agent = GeminiAgent()
        print(f"✓ Agent initialized (Model: {agent.model_name})\n")
        
        # Set a system instruction for the chat
        system_instruction = """You are a helpful assistant for creating educational content including courses, lessons, assignments, and quizzes.

When to call functions:
1. generate_course: When user asks to create/generate a course AND provides a topic. If no topic is given, ask for clarification.
2. generate_course_introduction: When user asks to add or create an introduction for a course. Requires course title and description.
3. generate_lesson: When user asks to create lessons for a course. Use course context from the conversation if available. If duration_weeks or sessions_per_week are not provided, ask the user for this information. Generate multiple lessons that follow scaffolding/cumulative organization.
4. generate_assignment: When user asks to create an assignment from material content. The material content will be in the user's message.
5. generate_quiz: When user asks to create a quiz from material content. The material content will be in the user's message.

Keep your responses concise and conversational. When calling functions, use all available information from the conversation context and user's message."""
        
        # Start a chat session with function calling enabled
        print("Starting chat session with function calling...")
        chat, generation_config = agent.start_chat_session(
            system_instruction=system_instruction,
            temperature=0.7,
            enable_function_calling=True  # Enable AI-driven function calling
        )
        print("✓ Chat session started with function calling enabled\n")
        print("✓ AI can automatically detect when to generate courses, lessons, assignments, and quizzes\n")
        
        print("Chat started! Type your message:\n")
        
        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()
                
                # Check for exit commands
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\nGoodbye! 👋\n")
                    break
                
                if not user_input:
                    print("Please enter a message.\n")
                    continue
                
                # Send message to chat session
                # ChatSession automatically includes previous conversation history
                print("\nAI: ", end="", flush=True)
                
                # Send message (non-streaming first to check for function calls)
                # Add retry logic for network errors
                max_retries = 3
                retry_delay = 2  # seconds
                response = None
                print(f"Sending message for user: {user_input}")
                for attempt in range(max_retries):
                    try:
                        response = chat.send_message(
                            user_input,
                            generation_config=generation_config,
                            stream=False  # Need to check for function calls first
                        )
                        break  # Success, exit retry loop
                    except (google_exceptions.ServiceUnavailable, 
                            google_exceptions.InternalServerError,
                            Exception) as e:
                        error_msg = str(e).lower()
                        # Check if it's a network/connectivity error
                        if 'unavailable' in error_msg or 'recvmsg' in error_msg or 'address' in error_msg:
                            if attempt < max_retries - 1:
                                print(f"\n⚠️  Network error (attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay} seconds...")
                                time.sleep(retry_delay)
                                retry_delay *= 2  # Exponential backoff
                                continue
                            else:
                                print(f"\n❌ Network error after {max_retries} attempts.")
                                print("   This is likely a connectivity issue, not a code problem.")
                                print("   Troubleshooting:")
                                print("   - Check your internet connection")
                                print("   - Verify GCP_PROJECT_ID and credentials are correct")
                                print("   - Check if Vertex AI service is accessible")
                                print("   - Try again in a few moments\n")
                                raise
                        else:
                            # Not a network error, re-raise immediately
                            raise
                
                # First, try to get text response
                # If it fails with function_call error, then handle as function call
                has_function_call = False
                function_calls = []
                text_response = None
                
                try:
                    # Try to access text - if it fails, might be a function call
                    text_response = response.text
                except (ValueError, AttributeError) as e:
                    # Check if error is about function_call (not just missing text)
                    error_msg = str(e)
                    if 'function_call' in error_msg.lower() or 'function' in error_msg.lower():
                        # This is likely a function call response
                        has_function_call = True
                    else:
                        # Some other error, log it
                        logger.warning(f"Unexpected error getting text: {e}")
                
                # If we couldn't get text, check for function calls
                if has_function_call or not text_response:
                    # Check for function calls in the response structure
                    try:
                        if hasattr(response, 'candidates') and response.candidates:
                            for candidate in response.candidates:
                                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                                    for part in candidate.content.parts:
                                        # Check if part has function_call
                                        if hasattr(part, 'function_call'):
                                            func_call = part.function_call
                                            
                                            # Skip if function_call is None or empty
                                            if not func_call:
                                                continue
                                            
                                            # Extract function name
                                            func_name = None
                                            if hasattr(func_call, 'name') and func_call.name:
                                                func_name = func_call.name
                                            elif isinstance(func_call, dict) and func_call.get('name'):
                                                func_name = func_call.get('name')
                                            
                                            # Only treat as function call if name exists and is not empty
                                            if func_name and func_name.strip():
                                                has_function_call = True
                                                function_calls.append(func_call)
                    except Exception as e:
                        logger.debug(f"Error checking for function calls: {e}")
                    
                    # Also check direct function_calls attribute
                    if not function_calls and hasattr(response, 'function_calls') and response.function_calls:
                        # Validate that function_calls actually have names
                        valid_calls = []
                        for call in response.function_calls:
                            func_name = None
                            if hasattr(call, 'name') and call.name:
                                func_name = call.name
                            elif isinstance(call, dict) and call.get('name'):
                                func_name = call.get('name')
                            
                            if func_name and func_name.strip():
                                valid_calls.append(call)
                        
                        if valid_calls:
                            has_function_call = True
                            function_calls = valid_calls
                
                # Only handle as function call if we actually found valid function calls
                if has_function_call and function_calls:
                    print(f"[AI detected function call request - calling function...]\n")
                    
                    # Process each function call
                    for function_call in function_calls:
                        # Extract function name and args
                        if hasattr(function_call, 'name'):
                            function_name = function_call.name
                            function_args = function_call.args if hasattr(function_call, 'args') else {}
                        else:
                            # Handle dict-like structure
                            function_name = function_call.get('name', '') if isinstance(function_call, dict) else getattr(function_call, 'name', '')
                            function_args = function_call.get('args', {}) if isinstance(function_call, dict) else (getattr(function_call, 'args', {}) if hasattr(function_call, 'args') else {})
                        
                        # Only proceed if function name is valid
                        if not function_name:
                            print("[Warning: Function call detected but no function name found]\n")
                            continue
                        
                        print(f"Executing: {function_name}\n")
                        
                        # Handle the function call
                        if function_name == "generate_course":
                            # Extract the user's original request
                            course_request = function_args.get("user_request") if isinstance(function_args, dict) else user_input
                            
                            # Call Level 2 AI for structured course generation
                            print("Generating structured course data...\n")
                            course_data = await agent.handle_course_generation(
                                user_request=course_request,
                                system_instruction="You are an expert course creator. Generate comprehensive course outlines.",
                                temperature=0.7
                            )
                            
                            # Display the generated course data
                            print(f"\n✓ Course generated successfully!")
                            print("\n[Structured Course Data Generated]")
                            print(json.dumps(course_data, indent=2))
                            print()
                            print("Course generation complete! You can ask me to modify anything or continue with your next request.\n")
                        
                        elif function_name == "generate_course_introduction":
                            # Extract parameters
                            if isinstance(function_args, dict):
                                course_title = function_args.get("course_title", "")
                                course_description = function_args.get("course_description", "")
                                intro_request = function_args.get("user_request", user_input)
                            else:
                                course_title = ""
                                course_description = ""
                                intro_request = user_input
                            
                            print("Generating course introduction...\n")
                            introduction_data = await agent.handle_course_introduction_generation(
                                course_title=course_title,
                                course_description=course_description,
                                user_request=intro_request,
                                temperature=0.7
                            )
                            
                            print(f"\n✓ Course introduction generated successfully!")
                            print("\n[Structured Course Introduction Data Generated]")
                            print(json.dumps(introduction_data, indent=2))
                            print()
                            print("Course introduction generation complete!\n")
                        
                        elif function_name == "generate_lesson":
                            # Extract parameters (all optional - AI can use conversation context)
                            if isinstance(function_args, dict):
                                course_title = function_args.get("course_title", "")
                                course_description = function_args.get("course_description", "")
                                duration_weeks = function_args.get("duration_weeks", None)
                                sessions_per_week = function_args.get("sessions_per_week", None)
                                lesson_request = function_args.get("user_request", user_input)
                            else:
                                course_title = ""
                                course_description = ""
                                duration_weeks = None
                                sessions_per_week = None
                                lesson_request = user_input
                            
                            print("Generating lessons for the course...\n")
                            lessons_data = await agent.handle_lesson_generation(
                                course_title=course_title,
                                course_description=course_description,
                                duration_weeks=duration_weeks,
                                sessions_per_week=sessions_per_week,
                                user_request=lesson_request,
                                temperature=0.7
                            )
                            
                            print(f"\n✓ Lessons generated successfully!")
                            print(f"\n[Generated {len(lessons_data.get('lessons', []))} lessons]")
                            print("\n[Structured Lessons Data Generated]")
                            print(json.dumps(lessons_data, indent=2))
                            print()
                            print("Lesson generation complete!\n")
                        
                        elif function_name == "generate_assignment":
                            # Extract user request (includes material content)
                            if isinstance(function_args, dict):
                                assignment_request = function_args.get("user_request", user_input)
                            else:
                                assignment_request = user_input
                            
                            print("Generating assignment...\n")
                            assignment_data = await agent.handle_assignment_generation(
                                user_request=assignment_request,
                                temperature=0.7
                            )
                            
                            print(f"\n✓ Assignment generated successfully!")
                            print("\n[Structured Assignment Data Generated]")
                            print(json.dumps(assignment_data, indent=2))
                            print()
                            print("Assignment generation complete!\n")
                        
                        elif function_name == "generate_quiz":
                            # Extract user request (includes material content)
                            if isinstance(function_args, dict):
                                quiz_request = function_args.get("user_request", user_input)
                            else:
                                quiz_request = user_input
                            
                            print("Generating quiz...\n")
                            quiz_data = await agent.handle_quiz_generation(
                                user_request=quiz_request,
                                temperature=0.7
                            )
                            
                            print(f"\n✓ Quiz generated successfully!")
                            print("\n[Structured Quiz Data Generated]")
                            print(json.dumps(quiz_data, indent=2))
                            print()
                            print("Quiz generation complete!\n")
                        
                        else:
                            print(f"[Warning: Unknown function '{function_name}']\n")
                else:
                    # No function call - normal text response
                    # Try to get text response safely
                    try:
                        if hasattr(response, 'text'):
                            text = response.text
                            if text:
                                print(text)
                            else:
                                # No text, try streaming
                                stream_response = chat.send_message(
                                    user_input,
                                    generation_config=generation_config,
                                    stream=True
                                )
                                for chunk in stream_response:
                                    if chunk.text:
                                        print(chunk.text, end="", flush=True)
                        else:
                            # No text attribute, use streaming
                            stream_response = chat.send_message(
                                user_input,
                                generation_config=generation_config,
                                stream=True
                            )
                            for chunk in stream_response:
                                if chunk.text:
                                    print(chunk.text, end="", flush=True)
                    except (ValueError, AttributeError) as e:
                        # Response has function call but we're treating it as text
                        # This shouldn't happen, but handle gracefully
                        print(f"\n[Note: Response contains function call, not text]")
                        logger.warning(f"Unexpected response type: {e}")
                    
                    print("\n\n")
                
                # Note: ChatSession automatically stores the user message and AI response
                # No need to manually manage conversation_history!
                
            except KeyboardInterrupt:
                print("\n\nChat interrupted. Goodbye! 👋\n")
                break
            except EOFError:
                print("\n\nGoodbye! 👋\n")
                break
                
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    import asyncio
    import sys
    
    # Configure logging for test output (only show warnings and errors)
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Suppress deprecation warnings from Vertex AI SDK
    import warnings
    warnings.filterwarnings('ignore', category=UserWarning, module='vertexai')
    
    # Set up Django environment if needed (for config to work)
    try:
        import django
        from django.conf import settings
        if not settings.configured:
            # Try to configure Django
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
            django.setup()
    except Exception as e:
        print(f"Warning: Could not configure Django settings: {e}")
        print("Make sure environment variables are set or Django is configured.\n")
    
    # Run interactive chat
    try:
        asyncio.run(interactive_chat())
    except KeyboardInterrupt:
        print("\n\nChat interrupted. Goodbye! 👋")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nError: {e}")
        sys.exit(1)

