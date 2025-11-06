"""
GeminiService - Base reusable service for Google Vertex AI (Gemini) interactions

This is a generic, reusable service that can be used for any AI task requiring:
- System instructions
- Structured output (optional)
- Direct Gemini API calls (no function calling)

Usage:
    from ai.gemini_service import GeminiService
    
    service = GeminiService()
    
    # Unstructured output
    response = service.generate(
        system_instruction="You are a helpful assistant.",
        prompt="Explain quantum computing",
        temperature=0.7
    )
    
    # Structured output (JSON schema)
    response = service.generate(
        system_instruction="You are a grading assistant.",
        prompt="Grade this essay: ...",
        response_schema={
            "type": "object",
            "properties": {
                "score": {"type": "number"},
                "feedback": {"type": "string"}
            }
        }
    )

Direct Testing:
    Run this file directly to test:
    python -m ai.gemini_service
    
    Or from Django shell:
    from ai.gemini_service import GeminiService
    service = GeminiService()
    service.test()
"""
import logging
import json
import os
from typing import Dict, List, Optional, Any
from google.cloud import aiplatform
from google.oauth2 import service_account
from vertexai.generative_models import GenerativeModel
from google.api_core import exceptions as google_exceptions
from decouple import config

logger = logging.getLogger(__name__)


class GeminiService:
    """
    Base reusable service for Google Vertex AI Gemini API interactions.
    
    This service provides a simple interface for generating content with:
    - System instructions
    - Optional structured output (JSON schema)
    - Configurable temperature and other parameters
    
    Designed to be used by domain-specific services (e.g., GeminiGrader)
    that handle business logic while this service handles the AI API interaction.
    """
    
    def __init__(self):
        """
        Initialize Vertex AI client.
        
        Reads configuration from environment variables:
        - GCP_PROJECT_ID: Google Cloud project ID
        - VERTEX_AI_LOCATION: Region (default: us-central1)
        - GEMINI_MODEL: Model name (default: gemini-2.0-flash-001)
        - GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON (optional)
        """
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
                logger.error(f"Failed to initialize Vertex AI: {e}", exc_info=True)
                raise
    
    def _get_credentials(self) -> Optional[service_account.Credentials]:
        """
        Get service account credentials if available.
        
        Checks:
        1. GOOGLE_APPLICATION_CREDENTIALS environment variable
        2. Default location: .credentials/vertex-ai-service-account.json
        
        Returns:
            Service account credentials or None if not found
        """
        creds_path = config('GOOGLE_APPLICATION_CREDENTIALS', default=None)
        
        # If not set, try default location
        if not creds_path:
            try:
                from django.conf import settings
                base_dir = settings.BASE_DIR
            except:
                # Fallback: calculate from current file location
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
        
        return None
    
    def _get_model(self, system_instruction: Optional[str] = None) -> GenerativeModel:
        """
        Get GenerativeModel instance.
        
        Args:
            system_instruction: Optional system instruction to pass to model
            
        Returns:
            Configured GenerativeModel instance
        """
        model_kwargs = {}
        
        # Add system instruction if provided
        if system_instruction:
            model_kwargs['system_instruction'] = system_instruction
        
        return GenerativeModel(
            model_name=self.model_name,
            **model_kwargs
        )
    
    def generate(
        self,
        system_instruction: str,
        prompt: str,
        response_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate content using Gemini API.
        
        Args:
            system_instruction: System instruction for the AI (required)
            prompt: User prompt/input (required)
            response_schema: Optional JSON schema for structured output
            temperature: Temperature for generation (0.0-1.0, default: 0.7)
            max_tokens: Maximum tokens in response (optional)
            **kwargs: Additional generation config parameters
            
        Returns:
            Dictionary with:
            - 'raw': Raw response text
            - 'parsed': Parsed JSON if schema provided, else None
            - 'model': Model name used
            
        Raises:
            ValueError: If required parameters are missing
            Exception: If API call fails
        """
        if not system_instruction:
            raise ValueError("system_instruction is required")
        if not prompt:
            raise ValueError("prompt is required")
        
        try:
            # Get model with system instruction
            model = self._get_model(system_instruction=system_instruction)
            
            # Build generation config
            generation_config = {
                'temperature': temperature,
            }
            
            if max_tokens:
                generation_config['max_output_tokens'] = max_tokens
            
            # Add any additional kwargs
            generation_config.update(kwargs)
            
            # For structured output, include schema in prompt and request JSON format
            final_prompt = prompt
            if response_schema:
                # Add schema to prompt and request JSON output
                schema_json = json.dumps(response_schema, indent=2)
                final_prompt = f"""{prompt}

IMPORTANT: Please respond with valid JSON matching this schema:
{schema_json}

Return ONLY valid JSON, no additional text before or after."""
            
            # Generate content
            logger.debug(f"Generating content with model: {self.model_name}")
            logger.debug(f"System instruction: {system_instruction[:100]}...")
            logger.debug(f"Prompt: {final_prompt[:100]}...")
            
            response = model.generate_content(
                final_prompt,
                generation_config=generation_config
            )
            
            # Extract text
            raw_text = response.text if hasattr(response, 'text') else str(response)
            
            # Parse JSON if schema was provided
            parsed_data = None
            if response_schema:
                try:
                    # Clean the response - remove markdown code blocks if present
                    cleaned_text = raw_text.strip()
                    if cleaned_text.startswith('```json'):
                        cleaned_text = cleaned_text[7:]  # Remove ```json
                    elif cleaned_text.startswith('```'):
                        cleaned_text = cleaned_text[3:]  # Remove ```
                    
                    if cleaned_text.endswith('```'):
                        cleaned_text = cleaned_text[:-3]  # Remove closing ```
                    
                    cleaned_text = cleaned_text.strip()
                    
                    parsed_data = json.loads(cleaned_text)
                    logger.debug(f"Parsed JSON response: {parsed_data}")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    logger.error(f"Raw response: {raw_text}")
                    raise ValueError(f"Invalid JSON response from AI: {e}")
            
            return {
                'raw': raw_text,
                'parsed': parsed_data,
                'model': self.model_name
            }
            
        except google_exceptions.GoogleAPIError as e:
            logger.error(f"Google API error: {e}", exc_info=True)
            raise Exception(f"Gemini API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in generate: {e}", exc_info=True)
            raise
    
    def test(self, test_prompt: Optional[str] = None):
        """
        Direct test function for the service.
        
        Can be called directly to test the service:
        - From command line: python -m ai.gemini_service
        - From Django shell: GeminiService().test()
        
        Args:
            test_prompt: Optional custom test prompt, defaults to simple test
        """
        print("\n" + "="*60)
        print("🧪 Testing GeminiService")
        print("="*60)
        
        if not self.project_id:
            print("❌ GCP_PROJECT_ID not set!")
            print("   Set it in your .env file or environment variables")
            return
        
        print(f"✅ Project ID: {self.project_id}")
        print(f"✅ Location: {self.location}")
        print(f"✅ Model: {self.model_name}")
        print()
        
        # Test 1: Simple unstructured output
        print("Test 1: Simple unstructured output")
        print("-" * 60)
        try:
            response = self.generate(
                system_instruction="You are a helpful assistant.",
                prompt=test_prompt or "Say hello and briefly explain what you can do.",
                temperature=0.7
            )
            print(f"✅ Success!")
            print(f"Response: {response['raw'][:200]}...")
            print()
        except Exception as e:
            print(f"❌ Failed: {e}")
            print()
        
        # Test 2: Structured output with JSON schema
        print("Test 2: Structured output (JSON schema)")
        print("-" * 60)
        try:
            schema = {
                "type": "object",
                "properties": {
                    "greeting": {"type": "string"},
                    "capabilities": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["greeting", "capabilities"]
            }
            
            response = self.generate(
                system_instruction="You are a helpful assistant.",
                prompt=test_prompt or "Say hello and list 3 things you can do.",
                response_schema=schema,
                temperature=0.7
            )
            
            print(f"✅ Success!")
            print(f"Raw response: {response['raw']}")
            print(f"Parsed JSON: {json.dumps(response['parsed'], indent=2)}")
            print()
        except Exception as e:
            print(f"❌ Failed: {e}")
            print()
        
        print("="*60)
        print("✅ Testing complete!")
        print("="*60 + "\n")


# Direct test execution
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize service
    service = GeminiService()
    
    # Run tests
    service.test()
