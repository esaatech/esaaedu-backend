"""
ChatService - Simple chat service using Vertex AI ChatSession API
No schemas, no function calling - just pure chat with native history management
"""
import logging
import os
from typing import Optional, Tuple
from google.cloud import aiplatform
from google.oauth2 import service_account
from vertexai.generative_models import GenerativeModel, ChatSession
from decouple import config

logger = logging.getLogger(__name__)


class ChatService:
    """
    Simple chat service for Vertex AI Gemini models
    Uses native ChatSession API for conversation history management
    """
    
    def __init__(self):
        """Initialize Vertex AI client"""
        self.project_id = config('GCP_PROJECT_ID', default=None)
        self.location = config('VERTEX_AI_LOCATION', default='us-central1')
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
        creds_path = config('GOOGLE_APPLICATION_CREDENTIALS', default=None)
        
        if not creds_path:
            try:
                from django.conf import settings
                base_dir = settings.BASE_DIR
            except:
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
        
        return None
    
    def start_chat(
        self,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Tuple[ChatSession, dict]:
        """
        Start a new chat session with native history management
        
        Args:
            system_instruction: Optional system instruction for the chat
            temperature: Creativity level (0.0-1.0)
            
        Returns:
            Tuple of (ChatSession object, generation_config dict)
            ChatSession automatically manages conversation history
        """
        try:
            # Create model
            if system_instruction:
                model = GenerativeModel(self.model_name, system_instruction=system_instruction)
            else:
                model = GenerativeModel(self.model_name)
            
            # Start chat session (automatically manages conversation history)
            chat = model.start_chat()
            
            # Generation config for messages
            generation_config = {"temperature": temperature}
            
            return chat, generation_config
            
        except Exception as e:
            logger.error(f"Error starting chat: {e}")
            raise
    
    def send_message(
        self,
        chat: ChatSession,
        message: str,
        generation_config: dict,
        stream: bool = False,
    ) -> str:
        """
        Send a message to the chat session
        
        Args:
            chat: ChatSession object
            message: User message
            generation_config: Generation configuration dict
            stream: Whether to stream the response
            
        Returns:
            Response text (if not streaming) or None (if streaming)
        """
        try:
            if stream:
                # For streaming, we'll yield chunks
                response = chat.send_message(
                    message,
                    generation_config=generation_config,
                    stream=True
                )
                return response  # Return the generator
            else:
                # Non-streaming response
                response = chat.send_message(
                    message,
                    generation_config=generation_config,
                    stream=False
                )
                return response.text
                
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise


# ============================================================================
# INTERACTIVE CHAT - Run this file directly to chat with Gemini
# Usage: python ai/chat_service.py
# ============================================================================
async def interactive_chat():
    """Interactive chat with ChatService using native ChatSession API"""
    print("\n" + "="*70)
    print("CHAT SERVICE - INTERACTIVE CHAT")
    print("="*70)
    print("Type your messages below. Type 'quit', 'exit', or Ctrl+C to end the chat.\n")
    
    try:
        # Initialize service
        print("Initializing ChatService...")
        service = ChatService()
        print(f"✓ Service initialized (Model: {service.model_name})\n")
        
        # Set a system instruction for the chat
        system_instruction = "You are a helpful and friendly assistant. Keep your responses concise and conversational."
        
        # Start a chat session (ChatSession automatically manages conversation history)
        print("Starting chat session...")
        chat, generation_config = service.start_chat(
            system_instruction=system_instruction,
            temperature=0.7
        )
        print("✓ Chat session started (conversation history managed by Vertex AI)\n")
        
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
                
                # Show AI is thinking
                print("\nAI: ", end="", flush=True)
                
                # Send message to chat session and stream response
                # ChatSession automatically includes previous conversation history
                full_response = ""
                response = chat.send_message(
                    user_input,
                    generation_config=generation_config,
                    stream=True
                )
                
                # Stream the response chunks
                for chunk in response:
                    if chunk.text:
                        print(chunk.text, end="", flush=True)
                        full_response += chunk.text
                
                print("\n\n")  # Add spacing after response
                
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
    
    # Configure logging
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Suppress deprecation warnings
    import warnings
    warnings.filterwarnings('ignore', category=UserWarning, module='vertexai')
    
    # Set up Django environment if needed
    try:
        import django
        from django.conf import settings
        if not settings.configured:
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
            django.setup()
    except Exception as e:
        print(f"Warning: Could not configure Django settings: {e}")
        print("Make sure environment variables are set or Django is configured.\n")
    
    # Run interactive chat
    try:
        asyncio.run(interactive_chat())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nTest failed with error: {e}")
        sys.exit(1)

