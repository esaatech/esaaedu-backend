"""
GeminiService - Main service class for Google Vertex AI (Gemini) integration
"""
import logging
import json
import os
from typing import Dict, List, Optional, Any, AsyncGenerator
from google.cloud import aiplatform
from google.oauth2 import service_account
from vertexai.generative_models import GenerativeModel
from decouple import config

logger = logging.getLogger(__name__)


class GeminiService:
    """
    Service for interacting with Google Vertex AI Gemini models
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
            # Get project root: ai/services.py -> ai/ -> backend/ -> project root
            # Or use BASE_DIR from Django settings if available
            try:
                from django.conf import settings
                base_dir = settings.BASE_DIR
            except:
                # Fallback: calculate from current file location
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            default_path = os.path.join(base_dir, '.credentials', 'vertex-ai-service-account.json')
            if os.path.exists(default_path):
                creds_path = default_path
                logger.info(f"Found Vertex AI credentials at: {creds_path}")
        
        if creds_path and os.path.exists(creds_path):
            try:
                credentials = service_account.Credentials.from_service_account_file(creds_path)
                logger.info(f"Loaded Vertex AI credentials from: {creds_path}")
                return credentials
            except Exception as e:
                logger.warning(f"Failed to load credentials from {creds_path}: {e}")
        else:
            if creds_path:
                logger.warning(f"Credentials file not found at: {creds_path}")
        
        # Return None to use default credentials (for Cloud Run)
        return None
    
    def _get_model(self, system_instruction: Optional[str] = None) -> GenerativeModel:
        """
        Get the configured Gemini model
        
        Args:
            system_instruction: Optional system instruction to include in the model
        """
        if system_instruction:
            return GenerativeModel(self.model_name, system_instruction=system_instruction)
        return GenerativeModel(self.model_name)
    
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
