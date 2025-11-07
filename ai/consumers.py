"""
WebSocket consumers for Django Channels - AI chat interface
"""
import json
import logging
import time
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from firebase_admin import auth
import firebase_admin
from .models import AIConversation
from .gemini_agent import GeminiAgent
from .prompts import get_prompt_for_type
from google.api_core import exceptions as google_exceptions
from courses.models import Course

logger = logging.getLogger(__name__)
User = get_user_model()


def ensure_firebase_initialized():
    """Ensure Firebase is initialized before use"""
    if not firebase_admin._apps:
        try:
            from backend.settings import initialize_firebase
            initialize_firebase()
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            return False
    return True


@database_sync_to_async
def verify_firebase_token(token):
    """
    Verify Firebase ID token and return decoded token.
    
    Args:
        token: Firebase ID token string
    
    Returns:
        dict: Decoded token with user info
    
    Raises:
        ValueError: If token is invalid
    """
    if not ensure_firebase_initialized():
        raise ValueError("Firebase not initialized")
    
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except auth.InvalidIdTokenError as e:
        logger.warning(f"Invalid Firebase token: {e}")
        raise ValueError("Invalid authentication token")
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise ValueError(f"Authentication failed: {e}")


@database_sync_to_async
def get_or_create_user(decoded_token):
    """
    Get or create Django user from Firebase token.
    
    Args:
        decoded_token: Decoded Firebase token
    
    Returns:
        User: Django user instance
    """
    firebase_uid = decoded_token.get('uid')
    email = decoded_token.get('email')
    
    if not firebase_uid or not email:
        raise ValueError("Invalid token: missing required fields")
    
    try:
        user = User.objects.get(firebase_uid=firebase_uid)
    except User.DoesNotExist:
        # Create new user (simplified - role should be set via signup endpoint)
        name = decoded_token.get('name', '')
        name_parts = name.split(' ', 1) if name else ['', '']
        
        user = User.objects.create_user(
            firebase_uid=firebase_uid,
            email=email,
            first_name=name_parts[0],
            last_name=name_parts[1] if len(name_parts) > 1 else '',
            username=email,
            role=User.Role.STUDENT  # Default role
        )
        logger.info(f"Created new user via WebSocket: {email}")
    
    return user


@database_sync_to_async
def get_or_create_conversation(user, conversation_type, conversation_id=None, context=None):
    """
    Get existing conversation or create new one.
    
    Args:
        user: Django user instance
        conversation_type: Type of conversation
        conversation_id: Optional UUID of existing conversation
        context: Optional context dict
    
    Returns:
        AIConversation: Conversation instance
    """
    if conversation_id:
        try:
            conversation = AIConversation.objects.get(
                id=conversation_id,
                user=user,
                is_active=True
            )
            return conversation
        except AIConversation.DoesNotExist:
            logger.warning(f"Conversation {conversation_id} not found, creating new one")
    
    # Create new conversation
    conversation = AIConversation.objects.create(
        user=user,
        conversation_type=conversation_type,
        context=context or {},
        messages=[]
    )
    return conversation


@database_sync_to_async
def save_conversation_message(conversation, role, content):
    """Save message to conversation"""
    conversation.add_message(role, content)
    return conversation


@database_sync_to_async
def save_generated_content(conversation, content):
    """Save generated content to conversation"""
    conversation.generated_content = content
    conversation.save()
    return conversation


@database_sync_to_async
def get_course_categories_sync():
    """Get course categories (wrapped for async context)"""
    from .prompts import get_course_categories
    return get_course_categories()


@database_sync_to_async
def get_prompt_for_type_sync(prompt_type, user_request, context=None):
    """Get prompt configuration (wrapped for async context)"""
    return get_prompt_for_type(prompt_type, user_request, context)


@database_sync_to_async
def get_course_and_validate_ownership(course_id, user):
    """
    Get course and validate user owns it
    
    Args:
        course_id: UUID of the course
        user: Django user instance
        
    Returns:
        Course: Course instance if found and user owns it
        
    Raises:
        Course.DoesNotExist: If course not found
        PermissionError: If user doesn't own the course
    """
    try:
        course = Course.objects.select_related('teacher').get(id=course_id)
    except Course.DoesNotExist:
        raise Course.DoesNotExist(f"Course {course_id} not found")
    
    # Check ownership
    if course.teacher != user:
        raise PermissionError(f"User {user.email} does not own course {course_id}")
    
    return course


class BaseAIConsumer(AsyncWebsocketConsumer):
    """
    Base consumer for AI chat functionality.
    Handles authentication, connection management, and common functionality.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.conversation = None
        self.gemini_service = None
        self.authenticated = False
    
    async def connect(self):
        """Handle WebSocket connection"""
        try:
            # Accept the connection first
            await self.accept()
            logger.info(f"WebSocket connection opened: {self.scope.get('path', 'unknown')}")
            
            # Send welcome message (optional, but helps debug)
            await self.send_json({
                'type': 'connected',
                'message': 'WebSocket connected. Please authenticate.'
            })
            
        except Exception as e:
            logger.error(f"Error in WebSocket connect: {e}", exc_info=True)
            # Don't raise - let the connection close gracefully
            try:
                await self.close()
            except:
                pass
            raise
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        logger.info(f"WebSocket connection closed: {close_code}")
    
    async def receive(self, text_data=None, bytes_data=None):
        """Handle messages from client - supports both text and binary"""
        try:
            # Handle text data (normal case)
            if text_data:
                data = json.loads(text_data)
            # Handle binary data (Cloud Run proxy case)
            elif bytes_data:
                # Try to decode bytes to string
                if isinstance(bytes_data, bytes):
                    text_data = bytes_data.decode('utf-8')
                elif isinstance(bytes_data, tuple):
                    # Cloud Run might send tuples - extract the actual data
                    text_data = bytes_data[0].decode('utf-8') if isinstance(bytes_data[0], bytes) else str(bytes_data[0])
                else:
                    text_data = str(bytes_data)
                data = json.loads(text_data)
            else:
                await self.send_error("No data received")
                return
            
            message_type = data.get('type', 'message')
            
            # Handle authentication
            if message_type == 'auth':
                await self.handle_auth(data)
                return
            
            # Require authentication for other messages
            if not self.authenticated:
                await self.send_error("Authentication required. Please send 'auth' message first.")
                await self.close()
                return
            
            # Route to appropriate handler
            if message_type == 'message':
                await self.handle_message(data)
            elif message_type == 'refinement':
                await self.handle_refinement(data)
            elif message_type == 'save':
                await self.handle_save(data)
            else:
                await self.send_error(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}, text_data: {text_data[:100] if text_data else None}, bytes_data: {bytes_data}")
            await self.send_error("Invalid JSON format")
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            await self.send_error(f"Internal error: {str(e)}")
    
    async def handle_auth(self, data):
        """Handle authentication message"""
        token = data.get('token')
        
        if not token:
            await self.send_error("Token is required for authentication")
            await self.close()
            return
        
        try:
            # Verify Firebase token
            decoded_token = await verify_firebase_token(token)
            
            # Get or create user
            self.user = await get_or_create_user(decoded_token)
            self.authenticated = True
            
            # Initialize Gemini agent
            self.gemini_service = GeminiAgent()
            
            await self.send_json({
                'type': 'auth_success',
                'message': 'Authentication successful'
            })
            
            logger.info(f"User authenticated via WebSocket: {self.user.email}")
            
        except ValueError as e:
            await self.send_error(f"Authentication failed: {str(e)}")
            await self.close()
        except Exception as e:
            logger.error(f"Auth error: {e}", exc_info=True)
            await self.send_error("Authentication error")
            await self.close()
    
    async def handle_message(self, data):
        """Handle message - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement handle_message")
    
    async def handle_refinement(self, data):
        """Handle refinement request - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement handle_refinement")
    
    async def handle_save(self, data):
        """Handle save request - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement handle_save")
    
    async def send_json(self, data):
        """Send JSON message to client"""
        await self.send(text_data=json.dumps(data))
    
    async def send_error(self, message):
        """Send error message to client"""
        await self.send_json({
            'type': 'error',
            'message': message
        })
    
    async def send_streaming(self, content):
        """Send streaming content chunk"""
        await self.send_json({
            'type': 'streaming',
            'content': content
        })
    
    async def send_complete(self, data, conversation_id=None):
        """Send complete response"""
        await self.send_json({
            'type': 'complete',
            'conversation_id': str(conversation_id) if conversation_id else None,
            'data': data
        })


class CourseGenerationConsumer(BaseAIConsumer):
    """
    Consumer for course generation via AI chat using GeminiAgent with function calling
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store ChatSession per conversation
        # Key: conversation_id (str), Value: (ChatSession, generation_config) tuple
        self.chat_sessions = {}
    
    async def _get_or_create_chat_session(self, conversation_id=None):
        """
        Get or create ChatSession for a conversation
        ChatSession manages conversation history automatically
        """
        session_key = str(conversation_id) if conversation_id else 'default'
        
        if session_key not in self.chat_sessions:
            # Create new chat session with function calling enabled
            # System instruction encourages immediate course generation when user requests it
            """
            system_instruction =""" """You are a helpful assistant for creating educational courses. 
When a user asks to create, generate, or make a course (even if they just provide a topic like "java" or "android"), 
you should IMMEDIATELY call the generate_course function. Do not ask for more details - use the information provided 
and generate a comprehensive course. Only ask questions if the user's request is completely unclear or ambiguous."""
            
            system_instruction = "You are a helpful and friendly assistant. Keep your responses concise and conversational."

            chat, generation_config = self.gemini_service.start_chat_session(
                system_instruction=system_instruction,
                temperature=0.7,
                enable_function_calling=True  # Enable AI-driven function calling
            )
            
            self.chat_sessions[session_key] = (chat, generation_config)
            logger.info(f"Created new ChatSession for conversation: {session_key}")
        
        return self.chat_sessions[session_key]
    
    async def _send_message_with_retry(self, chat, user_input, generation_config, max_retries=3):
        """
        Send message to ChatSession with retry logic for network errors
        """
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                response = chat.send_message(
                    user_input,
                    generation_config=generation_config,
                    stream=False  # Need to check for function calls first
                )
                return response
            except (google_exceptions.ServiceUnavailable, 
                    google_exceptions.InternalServerError,
                    Exception) as e:
                error_msg = str(e).lower()
                # Check if it's a network/connectivity error
                if 'unavailable' in error_msg or 'recvmsg' in error_msg or 'address' in error_msg:
                    if attempt < max_retries - 1:
                        logger.warning(f"Network error (attempt {attempt + 1}/{max_retries}). Retrying...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        logger.error(f"Network error after {max_retries} attempts")
                        raise
                else:
                    # Not a network error, re-raise immediately
                    raise
        
        # Should never reach here, but just in case
        raise Exception("Failed to send message after retries")
    
    async def _detect_function_calls(self, response):
        """
        Detect if response contains function calls
        Returns: (has_function_call: bool, function_calls: list)
        """
        has_function_call = False
        function_calls = []
        text_response = None
        
        # First, try to get text response
        try:
            text_response = response.text
        except (ValueError, AttributeError) as e:
            error_msg = str(e)
            if 'function_call' in error_msg.lower() or 'function' in error_msg.lower():
                has_function_call = True
            else:
                logger.warning(f"Unexpected error getting text: {e}")
        
        # If we couldn't get text, check for function calls
        if has_function_call or not text_response:
            # Check for function calls in the response structure
            try:
                if hasattr(response, 'candidates') and response.candidates:
                    for candidate in response.candidates:
                        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                            for part in candidate.content.parts:
                                if hasattr(part, 'function_call'):
                                    func_call = part.function_call
                                    if not func_call:
                                        continue
                                    
                                    # Extract function name
                                    func_name = None
                                    if hasattr(func_call, 'name') and func_call.name:
                                        func_name = func_call.name
                                    elif isinstance(func_call, dict) and func_call.get('name'):
                                        func_name = func_call.get('name')
                                    
                                    if func_name and func_name.strip():
                                        has_function_call = True
                                        function_calls.append(func_call)
            except Exception as e:
                logger.debug(f"Error checking for function calls: {e}")
            
            # Also check direct function_calls attribute
            if not function_calls and hasattr(response, 'function_calls') and response.function_calls:
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
        
        return has_function_call, function_calls, text_response
    
    async def _handle_function_call(self, function_call, user_input, conversation_id):
        """
        Handle function call execution (e.g., generate_course)
        """
        # Extract function name and args
        if hasattr(function_call, 'name'):
            function_name = function_call.name
            function_args = function_call.args if hasattr(function_call, 'args') else {}
        else:
            function_name = function_call.get('name', '') if isinstance(function_call, dict) else getattr(function_call, 'name', '')
            function_args = function_call.get('args', {}) if isinstance(function_call, dict) else (getattr(function_call, 'args', {}) if hasattr(function_call, 'args') else {})
        
        if not function_name:
            logger.warning("Function call detected but no function name found")
            return None
        
        logger.info(f"Executing function: {function_name}")
        
        # Handle course generation
        if function_name == "generate_course":
            # Extract the user's original request
            course_request = function_args.get("user_request") if isinstance(function_args, dict) else user_input
            
            # Notify client that function is being executed
            await self.send_json({
                'type': 'function_call',
                'function_name': function_name,
                'message': 'Generating course...'
            })
            
            # Call Level 2 AI for structured course generation
            course_data = await self.gemini_service.handle_course_generation(
                user_request=course_request,
                system_instruction="You are an expert course creator. Generate comprehensive course outlines.",
                temperature=0.7
            )
            
            # Save generated course data to conversation
            await save_generated_content(self.conversation, course_data)
            
            # Ensure course_data is a dict
            if not isinstance(course_data, dict):
                logger.error(f"course_data is not a dict: {type(course_data)}")
                raise ValueError("course_data must be a dictionary")
            
            # Send course_data with type: 'course_generated' (spread properties directly)
            # This matches what the user requested - just the course_data properties
            response_data = {
                'type': 'course_generated',
                **course_data  # Spread course_data properties directly
            }
            
            logger.info(f"Sending course data - Type: {response_data.get('type')}, Title: {response_data.get('title')}")
            await self.send_json(response_data)
            
            # Also send as 'complete' type for frontend compatibility (if needed)
            # The frontend can use either format
            await self.send_json({
                'type': 'complete',
                'conversation_id': str(self.conversation.id) if self.conversation else None,
                'data': course_data
            })
            
            return course_data
        
        return None
    
    async def handle_message(self, data):
        """Handle course generation request using GeminiAgent"""
        user_request = data.get('content', '').strip()
        conversation_id = data.get('conversation_id')
        context = data.get('context', {})
        
        if not user_request:
            await self.send_error("Content is required")
            return
        
        try:
            # Get or create conversation
            self.conversation = await get_or_create_conversation(
                self.user,
                'course_generation',
                conversation_id,
                context
            )
            
            # Save user message to database
            await save_conversation_message(self.conversation, 'user', user_request)
            
            # Get or create ChatSession for this conversation
            chat, generation_config = await self._get_or_create_chat_session(
                str(self.conversation.id)
            )
            
            # Send message to ChatSession with retry logic
            response = await self._send_message_with_retry(
                chat, user_request, generation_config
            )
            
            # Detect function calls
            has_function_call, function_calls, text_response = await self._detect_function_calls(response)
            
            # Handle function calls
            if has_function_call and function_calls:
                try:
                    for function_call in function_calls:
                        course_data = await self._handle_function_call(
                            function_call, user_request, str(self.conversation.id)
                        )
                        
                        # If course was generated, save assistant message
                        if course_data:
                            assistant_msg = f"Course generated: {course_data.get('title', 'Untitled Course')}"
                            await save_conversation_message(self.conversation, 'assistant', assistant_msg)
                            logger.info(f"Course generated successfully: {course_data.get('title')}")
                    
                    # Note: We don't send a follow-up message to chat after function execution
                    # The conversation continues naturally when the user sends their next message
                    return
                except Exception as e:
                    logger.error(f"Error handling function call: {e}", exc_info=True)
                    await self.send_error(f"Error generating course: {str(e)}")
                    return
            
            # Normal text response - stream it back to client
            if text_response:
                # Save full response
                await save_conversation_message(self.conversation, 'assistant', text_response)
                
                # Send only the content (simple format)
                await self.send_json({
                    'type': 'message',
                    'content': text_response
                })
            else:
                # Try streaming response
                stream_response = chat.send_message(
                    user_request,
                    generation_config=generation_config,
                    stream=True
                )
                
                full_response = ""
                for chunk in stream_response:
                    if chunk.text:
                        chunk_text = chunk.text
                        full_response += chunk_text
                        await self.send_streaming(chunk_text)
                
                # Save full streamed response
                if full_response:
                    await save_conversation_message(self.conversation, 'assistant', full_response)
                    
                    # Send completion - only the content
                    await self.send_json({
                        'type': 'message',
                        'content': full_response
                    })
        
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            await self.send_error(f"Error processing request: {str(e)}")
    
    async def handle_refinement(self, data):
        """Handle refinement request - same flow as handle_message"""
        refinement_request = data.get('content', '').strip()
        conversation_id = data.get('conversation_id')
        
        if not refinement_request:
            await self.send_error("Content is required")
            return
        
        # Treat refinement as a regular message
        await self.handle_message({
            'content': refinement_request,
            'conversation_id': conversation_id,
            'context': {}
        })
    
    async def handle_save(self, data):
        """Handle save/approve request"""
        # For course generation, "save" means the user approved the generated content
        # The content is already saved in the conversation
        # This could trigger creating the actual Course object, but that's handled by the frontend
        
        await self.send_json({
            'type': 'save_success',
            'message': 'Content approved',
            'conversation_id': str(self.conversation.id) if self.conversation else None
        })


class CourseManagementConsumer(BaseAIConsumer):
    """
    Consumer for course management via AI chat (introduction, lessons, assignments, quizzes)
    Requires course_id from URL path
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chat_sessions = {}
        self.course_id = None
        self.course = None
    
    async def connect(self):
        """Handle WebSocket connection and extract course_id from URL"""
        try:
            # Extract course_id from URL kwargs (from regex named group)
            import uuid
            kwargs = self.scope.get('url_route', {}).get('kwargs', {})
            course_id_str = kwargs.get('course_id')
            
            if not course_id_str:
                logger.error("Course ID not found in URL")
                await self.close(code=4004)  # Invalid path
                return
            
            try:
                course_id = uuid.UUID(course_id_str)
                self.course_id = course_id
            except ValueError:
                logger.error(f"Invalid course ID format: {course_id_str}")
                await self.send_error(f"Invalid course ID format: {course_id_str}")
                await self.close(code=4004)
                return
            
            # Accept connection
            await self.accept()
            logger.info(f"CourseManagementConsumer connection opened for course: {course_id}")
            
            await self.send_json({
                'type': 'connected',
                'message': 'WebSocket connected. Please authenticate.',
                'course_id': str(course_id)
            })
            
        except Exception as e:
            logger.error(f"Error in CourseManagementConsumer connect: {e}", exc_info=True)
            try:
                await self.close()
            except:
                pass
            raise
    
    async def handle_auth(self, data):
        """Handle authentication and validate course ownership"""
        token = data.get('token')
        
        if not token:
            await self.send_error("Token is required for authentication")
            await self.close()
            return
        
        try:
            # Verify Firebase token
            decoded_token = await verify_firebase_token(token)
            
            # Get or create user
            self.user = await get_or_create_user(decoded_token)
            
            # Validate course ownership
            if not self.course_id:
                await self.send_error("Course ID is required")
                await self.close()
                return
            
            self.course = await get_course_and_validate_ownership(self.course_id, self.user)
            self.authenticated = True
            
            # Initialize Gemini agent
            self.gemini_service = GeminiAgent()
            
            await self.send_json({
                'type': 'auth_success',
                'message': 'Authentication successful',
                'course_id': str(self.course_id),
                'course_title': self.course.title
            })
            
            logger.info(f"User authenticated for course management: {self.user.email}, course: {self.course.title}")
            
        except ValueError as e:
            await self.send_error(f"Authentication failed: {str(e)}")
            await self.close()
        except Exception as e:
            logger.error(f"Auth error: {e}", exc_info=True)
            await self.send_error("Authentication error")
            await self.close()
    
    async def _get_or_create_chat_session(self, conversation_id=None):
        """Get or create ChatSession for a conversation"""
        from .schemas import get_course_management_function_schema
        
        session_key = str(conversation_id) if conversation_id else 'default'
        
        if session_key not in self.chat_sessions:
            # Create new chat session with course management functions
            system_instruction = f"""You are a helpful assistant for managing the course "{self.course.title}". 
You can help generate course introductions, lessons, assignments, and quizzes for this course.
Be conversational and helpful. Ask clarifying questions if needed before generating content."""
            
            # Get function schema for course management (no generate_course)
            function_schemas = get_course_management_function_schema()
            
            chat, generation_config = self.gemini_service.start_chat_session(
                system_instruction=system_instruction,
                temperature=0.7,
                enable_function_calling=True,
                function_schemas=function_schemas
            )
            
            self.chat_sessions[session_key] = (chat, generation_config)
            logger.info(f"Created new ChatSession for course management: {session_key}")
        
        return self.chat_sessions[session_key]
    
    async def _send_message_with_retry(self, chat, user_input, generation_config, max_retries=3):
        """Send message to ChatSession with retry logic"""
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                response = chat.send_message(
                    user_input,
                    generation_config=generation_config,
                    stream=False
                )
                return response
            except (google_exceptions.ServiceUnavailable, 
                    google_exceptions.InternalServerError,
                    Exception) as e:
                error_msg = str(e).lower()
                if 'unavailable' in error_msg or 'recvmsg' in error_msg or 'address' in error_msg:
                    if attempt < max_retries - 1:
                        logger.warning(f"Network error (attempt {attempt + 1}/{max_retries}). Retrying...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        logger.error(f"Network error after {max_retries} attempts")
                        raise
                else:
                    raise
        
        raise Exception("Failed to send message after retries")
    
    async def _detect_function_calls(self, response):
        """Detect if response contains function calls"""
        has_function_call = False
        function_calls = []
        text_response = None
        
        try:
            text_response = response.text
        except (ValueError, AttributeError) as e:
            error_msg = str(e)
            if 'function_call' in error_msg.lower() or 'function' in error_msg.lower():
                has_function_call = True
        
        if has_function_call or not text_response:
            try:
                if hasattr(response, 'candidates') and response.candidates:
                    for candidate in response.candidates:
                        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                            for part in candidate.content.parts:
                                if hasattr(part, 'function_call'):
                                    func_call = part.function_call
                                    if func_call:
                                        func_name = None
                                        if hasattr(func_call, 'name') and func_call.name:
                                            func_name = func_call.name
                                        elif isinstance(func_call, dict) and func_call.get('name'):
                                            func_name = func_call.get('name')
                                        
                                        if func_name and func_name.strip():
                                            has_function_call = True
                                            function_calls.append(func_call)
            except Exception as e:
                logger.debug(f"Error checking for function calls: {e}")
            
            if not function_calls and hasattr(response, 'function_calls') and response.function_calls:
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
        
        return has_function_call, function_calls, text_response
    
    async def _handle_function_call(self, function_call, user_input, conversation_id):
        """Handle function call execution"""
        # Extract function name and args
        if hasattr(function_call, 'name'):
            function_name = function_call.name
            function_args = function_call.args if hasattr(function_call, 'args') else {}
        else:
            function_name = function_call.get('name', '') if isinstance(function_call, dict) else getattr(function_call, 'name', '')
            function_args = function_call.get('args', {}) if isinstance(function_call, dict) else (getattr(function_call, 'args', {}) if hasattr(function_call, 'args') else {})
        
        if not function_name:
            logger.warning("Function call detected but no function name found")
            return None
        
        logger.info(f"Executing function: {function_name} for course: {self.course_id}")
        
        # Handle course introduction generation
        if function_name == "generate_course_introduction":
            user_request = function_args.get("user_request") if isinstance(function_args, dict) else user_input
            course_title = function_args.get("course_title", self.course.title) if isinstance(function_args, dict) else self.course.title
            course_description = function_args.get("course_description", self.course.description) if isinstance(function_args, dict) else self.course.description
            
            await self.send_json({
                'type': 'function_call',
                'function_name': function_name,
                'message': 'Generating course introduction...'
            })
            
            introduction_data = await self.gemini_service.handle_course_introduction_generation(
                user_request=user_request,
                course_title=course_title,
                course_description=course_description,
                temperature=0.7
            )
            
            await save_generated_content(self.conversation, introduction_data)
            
            response_data = {
                'type': 'course_introduction_generated',
                'conversation_id': str(self.conversation.id) if self.conversation else None,
                **introduction_data
            }
            
            await self.send_json(response_data)
            return introduction_data
        
        # Handle lesson generation
        elif function_name == "generate_lesson":
            user_request = function_args.get("user_request") if isinstance(function_args, dict) else user_input
            course_title = function_args.get("course_title", self.course.title) if isinstance(function_args, dict) else self.course.title
            course_description = function_args.get("course_description", self.course.description) if isinstance(function_args, dict) else self.course.description
            duration_weeks = function_args.get("duration_weeks") if isinstance(function_args, dict) else None
            sessions_per_week = function_args.get("sessions_per_week") if isinstance(function_args, dict) else None
            
            await self.send_json({
                'type': 'function_call',
                'function_name': function_name,
                'message': 'Generating lessons...'
            })
            
            lessons_data = await self.gemini_service.handle_lesson_generation(
                user_request=user_request,
                course_title=course_title,
                course_description=course_description,
                duration_weeks=duration_weeks,
                sessions_per_week=sessions_per_week,
                temperature=0.7
            )
            
            await save_generated_content(self.conversation, lessons_data)
            
            response_data = {
                'type': 'lesson_generated',
                'conversation_id': str(self.conversation.id) if self.conversation else None,
                **lessons_data
            }
            
            await self.send_json(response_data)
            return lessons_data
        
        # Handle assignment generation
        elif function_name == "generate_assignment":
            user_request = function_args.get("user_request") if isinstance(function_args, dict) else user_input
            
            await self.send_json({
                'type': 'function_call',
                'function_name': function_name,
                'message': 'Generating assignment...'
            })
            
            assignment_data = await self.gemini_service.handle_assignment_generation(
                user_request=user_request,
                temperature=0.7
            )
            
            await save_generated_content(self.conversation, assignment_data)
            
            response_data = {
                'type': 'assignment_generated',
                'conversation_id': str(self.conversation.id) if self.conversation else None,
                **assignment_data
            }
            
            await self.send_json(response_data)
            return assignment_data
        
        # Handle quiz generation
        elif function_name == "generate_quiz":
            user_request = function_args.get("user_request") if isinstance(function_args, dict) else user_input
            
            await self.send_json({
                'type': 'function_call',
                'function_name': function_name,
                'message': 'Generating quiz...'
            })
            
            quiz_data = await self.gemini_service.handle_quiz_generation(
                user_request=user_request,
                temperature=0.7
            )
            
            await save_generated_content(self.conversation, quiz_data)
            
            response_data = {
                'type': 'quiz_generated',
                'conversation_id': str(self.conversation.id) if self.conversation else None,
                **quiz_data
            }
            
            await self.send_json(response_data)
            return quiz_data
        
        return None
    
    async def handle_message(self, data):
        """Handle course management request"""
        user_request = data.get('content', '').strip()
        conversation_id = data.get('conversation_id')
        context = data.get('context', {})
        
        if not user_request:
            await self.send_error("Content is required")
            return
        
        try:
            # Get or create conversation
            context['course_id'] = str(self.course_id)
            self.conversation = await get_or_create_conversation(
                self.user,
                'course_management',
                conversation_id,
                context
            )
            
            # Save user message
            await save_conversation_message(self.conversation, 'user', user_request)
            
            # Get or create ChatSession
            chat, generation_config = await self._get_or_create_chat_session(
                str(self.conversation.id)
            )
            
            # Send message with retry
            response = await self._send_message_with_retry(
                chat, user_request, generation_config
            )
            
            # Detect function calls
            has_function_call, function_calls, text_response = await self._detect_function_calls(response)
            
            # Handle function calls
            if has_function_call and function_calls:
                try:
                    for function_call in function_calls:
                        result = await self._handle_function_call(
                            function_call, user_request, str(self.conversation.id)
                        )
                        
                        if result:
                            assistant_msg = f"Generated {function_call.name if hasattr(function_call, 'name') else 'content'}"
                            await save_conversation_message(self.conversation, 'assistant', assistant_msg)
                    
                    return
                except Exception as e:
                    logger.error(f"Error handling function call: {e}", exc_info=True)
                    await self.send_error(f"Error generating content: {str(e)}")
                    return
            
            # Normal text response
            if text_response:
                await save_conversation_message(self.conversation, 'assistant', text_response)
                await self.send_json({
                    'type': 'message',
                    'content': text_response
                })
            else:
                # Try streaming
                stream_response = chat.send_message(
                    user_request,
                    generation_config=generation_config,
                    stream=True
                )
                
                full_response = ""
                for chunk in stream_response:
                    if chunk.text:
                        chunk_text = chunk.text
                        full_response += chunk_text
                        await self.send_streaming(chunk_text)
                
                if full_response:
                    await save_conversation_message(self.conversation, 'assistant', full_response)
                    await self.send_json({
                        'type': 'message',
                        'content': full_response
                    })
        
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            await self.send_error(f"Error processing request: {str(e)}")
    
    async def handle_refinement(self, data):
        """Handle refinement request"""
        refinement_request = data.get('content', '').strip()
        conversation_id = data.get('conversation_id')
        
        if not refinement_request:
            await self.send_error("Content is required")
            return
        
        await self.handle_message({
            'content': refinement_request,
            'conversation_id': conversation_id,
            'context': {}
        })
    
    async def handle_save(self, data):
        """Handle save/approve request"""
        await self.send_json({
            'type': 'save_success',
            'message': 'Content approved',
            'conversation_id': str(self.conversation.id) if self.conversation else None
        })
