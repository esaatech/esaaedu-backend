"""
GeminiService - Main service class for Google Vertex AI (Gemini) integration
"""
import logging
import json
from typing import Dict, List, Optional, Any, AsyncGenerator
from google.cloud import aiplatform
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
        self.model_name = config('GEMINI_MODEL', default='gemini-1.5-pro')
        
        if not self.project_id:
            logger.warning("GCP_PROJECT_ID not set, Vertex AI may not work correctly")
        
        # Initialize Vertex AI
        if self.project_id:
            try:
                aiplatform.init(project=self.project_id, location=self.location)
                logger.info(f"Vertex AI initialized for project: {self.project_id}, location: {self.location}")
            except Exception as e:
                logger.error(f"Failed to initialize Vertex AI: {e}")
    
    def _get_model(self) -> GenerativeModel:
        """Get the configured Gemini model"""
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
            model = self._get_model()
            
            generation_config = {
                "temperature": temperature,
            }
            if max_tokens:
                generation_config["max_output_tokens"] = max_tokens
            
            # Build request
            if system_instruction:
                response = model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    system_instruction=system_instruction,
                )
            else:
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
            model = self._get_model()
            
            generation_config = {
                "temperature": temperature,
            }
            
            if system_instruction:
                responses = model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    system_instruction=system_instruction,
                    stream=True,
                )
            else:
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
