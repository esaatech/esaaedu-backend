"""
WebSocket consumers for Django Channels - AI chat interface
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from firebase_admin import auth
import firebase_admin
from .models import AIConversation
from .gemini_agent import GeminiAgent
from .prompts import get_prompt_for_type

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
    
    async def receive(self, text_data):
        """Handle messages from client"""
        try:
            data = json.loads(text_data)
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
                
        except json.JSONDecodeError:
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
    Consumer for course generation via AI chat
    """
    
    async def test_chatbot(self, user_message: str, conversation_id=None):
        """
        TASK 1: Simple test chatbot - just echoes message with random number
        This is isolated from AI course generation for testing
        """
        import random
        
        # Get or create conversation for chat history
        self.conversation = await get_or_create_conversation(
            self.user,
            'course_generation',
            conversation_id,
            {}
        )
        
        # Save user message
        await save_conversation_message(self.conversation, 'user', user_message)
        
        # Generate echo response with random number
        random_id = random.randint(1000, 9999)
        response = f"Echo: {user_message} [Response ID: {random_id}]"
        
        # Save assistant response
        await save_conversation_message(self.conversation, 'assistant', response)
        
        # Send response back to client
        await self.send_json({
            'type': 'message',
            'role': 'assistant',
            'content': response,
            'conversation_id': str(self.conversation.id)
        })
    
    async def handle_message(self, data):
        """Handle course generation request"""
        user_request = data.get('content', '').strip()
        conversation_id = data.get('conversation_id')
        context = data.get('context', {})
        test_mode = data.get('test_mode', False)  # For Task 1: Basic Chatbot testing
        
        if not user_request:
            await self.send_error("Content is required")
            return
        
        # TASK 1: Test Chatbot Mode - Isolated simple echo chatbot
        # ALWAYS use test chatbot - AI completely disabled for Task 1
        if test_mode:
            # Remove /test prefix if present
            clean_request = user_request.replace('/test', '').strip() or user_request
            await self.test_chatbot(clean_request, conversation_id)
            return
        
        # TASK 1: DISABLED - If test_mode is false, still use test chatbot for now
        # This ensures AI is completely disabled during Task 1 testing
        await self.test_chatbot(user_request, conversation_id)
        return
    
    async def handle_refinement(self, data):
        """Handle refinement request - TASK 1: Also goes through test chatbot"""
        refinement_request = data.get('content', '').strip()
        conversation_id = data.get('conversation_id')
        
        if not refinement_request:
            await self.send_error("Content is required")
            return
        
        # TASK 1: ALL refinements go through test chatbot - AI completely disabled
        await self.test_chatbot(refinement_request, conversation_id)
        return
    
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
