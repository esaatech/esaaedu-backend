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
import time
from typing import Dict, List, Optional, Any, Union
from google.cloud import aiplatform
from google.oauth2 import service_account
from vertexai.generative_models import (
    GenerativeModel,
    Part,
    Tool,
    FunctionDeclaration,
    GenerationConfig,
)
from google.api_core import exceptions as google_exceptions
from decouple import config
from django.core.exceptions import ImproperlyConfigured

from ai.exceptions import GeminiServiceError, from_google_api_error, invalid_response_error

logger = logging.getLogger(__name__)

DEFAULT_RATE_LIMIT_MAX_ATTEMPTS = 4
DEFAULT_RATE_LIMIT_BASE_DELAY_SEC = 2.0


def _is_rate_limited_error(exc: BaseException) -> bool:
    if isinstance(exc, google_exceptions.ResourceExhausted):
        return True
    if isinstance(exc, GeminiServiceError) and exc.error_code == "rate_limited":
        return True
    return False


def _generate_with_retry(
    model,
    content_list,
    generation_config,
    *,
    max_attempts: int = DEFAULT_RATE_LIMIT_MAX_ATTEMPTS,
    base_delay_sec: float = DEFAULT_RATE_LIMIT_BASE_DELAY_SEC,
):
    """
    Call generate_content with exponential backoff on Vertex 429 / ResourceExhausted.
    """
    last_exc: Optional[google_exceptions.ResourceExhausted] = None
    for attempt in range(max_attempts):
        try:
            return model.generate_content(
                content_list,
                generation_config=generation_config,
            )
        except google_exceptions.ResourceExhausted as e:
            last_exc = e
            if attempt >= max_attempts - 1:
                break
            delay = base_delay_sec * (2 ** attempt)
            logger.warning(
                "Vertex AI rate limited (attempt %s/%s), retrying in %.1fs: %s",
                attempt + 1,
                max_attempts,
                delay,
                e,
            )
            time.sleep(delay)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("_generate_with_retry exhausted without response or exception")


def _raise_gemini_error(err: GeminiServiceError, *, context: str) -> None:
    """Send throttled Slack alert (once per error) and re-raise."""
    if not err.slack_notified:
        try:
            from error_alerts import notify_ai_failure

            notify_ai_failure(
                error_code=err.error_code,
                log_message=err.log_message,
                context=context,
                notify_admin=err.notify_admin,
            )
        except Exception as notify_exc:
            logger.warning("Gemini error notify step failed: %s", notify_exc, exc_info=True)
        err.slack_notified = True
    raise err


def _extract_text_parts(response) -> List[str]:
    """Collect text from all candidate content parts (skips function-call parts)."""
    if not getattr(response, "candidates", None):
        return []
    content = response.candidates[0].content
    if not getattr(content, "parts", None):
        return []
    text_parts: List[str] = []
    for part in content.parts:
        if hasattr(part, "function_call") and part.function_call:
            continue
        if hasattr(part, "text") and part.text:
            text_parts.append(part.text)
    return text_parts


def _extract_response_text(response) -> str:
    """
    Safely extract text from a Gemini response.

    response.text raises when multiple content parts are present (common on
    Gemini 2.5 thinking models). Prefer the last non-empty text part when
    multiple parts exist, since later parts are often the complete answer.
    """
    text_parts = _extract_text_parts(response)
    if text_parts:
        return text_parts[-1].strip() if len(text_parts) > 1 else text_parts[0].strip()
    if hasattr(response, "text"):
        try:
            return (response.text or "").strip()
        except ValueError:
            pass
    return str(response).strip()


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences from a JSON string."""
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _parse_json_from_text(text: str) -> Any:
    """Parse JSON from text, stripping markdown fences first."""
    return json.loads(_strip_json_fences(text))


def _parse_structured_response(raw_text: str, text_parts: List[str]) -> Any:
    """
    Parse structured JSON from model output.

    Tries the primary extracted text first, then each text part individually
    (last valid JSON wins) to handle duplicate multi-part grading responses.
    """
    candidates: List[str] = []
    if raw_text:
        candidates.append(raw_text)
    candidates.extend(text_parts)

    last_error: Optional[json.JSONDecodeError] = None
    seen: set[str] = set()
    for candidate in reversed(candidates):
        candidate = candidate.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            return _parse_json_from_text(candidate)
        except json.JSONDecodeError as e:
            last_error = e

    if last_error is not None:
        raise last_error
    raise ValueError("Empty response from AI")


def resolve_model_name(override: Optional[str] = None) -> str:
    """
    Resolve the Gemini model to use.

    Priority: explicit override (non-blank) → GEMINI_MODEL env (required).
    AIPromptTemplate.model_name and API request model_name should pass override here;
    blank/None means use the env default.
    """
    explicit = (override or "").strip()
    if explicit:
        return explicit
    value = (config("GEMINI_MODEL", default="") or "").strip()
    if not value:
        raise ImproperlyConfigured(
            "GEMINI_MODEL environment variable is required. "
            "Set it in .env (see env.example)."
        )
    return value


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
        - GEMINI_MODEL: Model name (required)
        - GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON (optional)
        """
        self.project_id = config('GCP_PROJECT_ID', default=None)
        self.location = config('VERTEX_AI_LOCATION', default='us-central1')
        self.model_name = resolve_model_name()
        
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
    
    def _get_model(
        self,
        system_instruction: Optional[str] = None,
        model_name: Optional[str] = None,
        tools: Optional[List[Tool]] = None,
    ) -> GenerativeModel:
        """
        Get GenerativeModel instance.
        
        Args:
            system_instruction: Optional system instruction to pass to model
            model_name: Optional model name to use (overrides self.model_name)
            tools: Optional list of Tool (e.g. for function calling)
            
        Returns:
            Configured GenerativeModel instance
        """
        model_kwargs = {}
        
        # Add system instruction if provided
        if system_instruction:
            model_kwargs['system_instruction'] = system_instruction
        
        if tools:
            model_kwargs['tools'] = tools
        
        model_to_use = resolve_model_name(model_name)
        
        return GenerativeModel(
            model_name=model_to_use,
            **model_kwargs
        )
    
    def generate(
        self,
        system_instruction: str,
        prompt: str,
        response_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        file_parts: Optional[List[Part]] = None,
        model_name: Optional[str] = None,
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
            file_parts: Optional list of Part objects (for file uploads like PDFs, videos)
            model_name: Optional model name to use (overrides default from config)
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
            # Get model with system instruction and optional model_name
            model = self._get_model(system_instruction=system_instruction, model_name=model_name)

            final_prompt = prompt
            generation_config: Union[Dict[str, Any], GenerationConfig]

            if response_schema:
                # Native Vertex structured output (preferred over prompt-only schema)
                config_kwargs: Dict[str, Any] = {
                    "temperature": temperature,
                    "response_mime_type": "application/json",
                    "response_schema": response_schema,
                }
                if max_tokens:
                    config_kwargs["max_output_tokens"] = max_tokens
                extra_config = {
                    k: v
                    for k, v in kwargs.items()
                    if k not in ("response_mime_type", "response_schema")
                }
                config_kwargs.update(extra_config)
                generation_config = GenerationConfig(**config_kwargs)
                final_prompt = (
                    f"{prompt}\n\n"
                    "Respond with valid JSON only, matching the required schema."
                )
            else:
                generation_config = {"temperature": temperature}
                if max_tokens:
                    generation_config["max_output_tokens"] = max_tokens
                generation_config.update(kwargs)

            # Build content list: prompt + file parts (if any)
            content_list = [final_prompt]
            if file_parts:
                content_list.extend(file_parts)
                logger.debug(f"Including {len(file_parts)} file part(s) in request")

            # Generate content
            logger.debug(f"Generating content with model: {resolve_model_name(model_name)}")
            logger.debug(f"System instruction: {system_instruction[:100]}...")
            logger.debug(f"Prompt: {final_prompt[:100]}...")

            try:
                response = _generate_with_retry(
                    model,
                    content_list,
                    generation_config,
                )
            except google_exceptions.GoogleAPIError as native_schema_err:
                if not response_schema or _is_rate_limited_error(native_schema_err):
                    raise
                # Fallback: prompt-based schema if native JSON mode is unsupported
                logger.warning(
                    "Native structured output failed, falling back to prompt schema: %s",
                    native_schema_err,
                )
                schema_json = json.dumps(response_schema, indent=2)
                fallback_prompt = f"""{prompt}

IMPORTANT: Please respond with valid JSON matching this schema:
{schema_json}

Return ONLY valid JSON, no additional text before or after."""
                fallback_config: Dict[str, Any] = {"temperature": temperature}
                if max_tokens:
                    fallback_config["max_output_tokens"] = max_tokens
                fallback_config.update(
                    {
                        k: v
                        for k, v in kwargs.items()
                        if k not in ("response_mime_type", "response_schema")
                    }
                )
                response = _generate_with_retry(
                    model,
                    [fallback_prompt] + (file_parts or []),
                    fallback_config,
                )
                final_prompt = fallback_prompt

            text_parts = _extract_text_parts(response)
            raw_text = _extract_response_text(response)

            # Parse JSON if schema was provided
            parsed_data = None
            if response_schema:
                try:
                    parsed_data = _parse_structured_response(raw_text, text_parts)
                    logger.debug(f"Parsed JSON response: {parsed_data}")
                except (json.JSONDecodeError, ValueError) as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    logger.error(f"Raw response: {raw_text}")
                    _raise_gemini_error(
                        invalid_response_error(
                            f"Invalid JSON response from AI: {e}",
                            cause=e if isinstance(e, json.JSONDecodeError) else None,
                        ),
                        context="GeminiService.generate",
                    )
            
            actual_model_name = resolve_model_name(model_name)
            
            return {
                'raw': raw_text,
                'parsed': parsed_data,
                'model': actual_model_name
            }
            
        except google_exceptions.GoogleAPIError as e:
            logger.error(f"Google API error: {e}", exc_info=True)
            _raise_gemini_error(from_google_api_error(e), context="GeminiService.generate")
        except GeminiServiceError:
            raise
        except ImproperlyConfigured:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in generate: {e}", exc_info=True)
            raise

    def generate_with_tools(
        self,
        system_instruction: str,
        prompt: str,
        tool_schemas: List[Dict[str, Any]],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        One-shot generate with function/tool declarations. Use for intent inference:
        model returns either a function_call (name + args) or plain text.
        tool_schemas: list of {"name": str, "description": str, "parameters": dict}
        where parameters is OpenAPI-style {"type": "object", "properties": {...}, "required": [...]}.
        Returns either {"function_call": {"name": str, "args": dict}} or {"text": str}.
        """
        if not tool_schemas:
            raise ValueError("tool_schemas is required for generate_with_tools")
        function_declarations = []
        for schema in tool_schemas:
            decl = FunctionDeclaration(
                name=schema["name"],
                description=schema["description"],
                parameters=schema.get("parameters", {"type": "object", "properties": {}}),
            )
            function_declarations.append(decl)
        tools = [Tool(function_declarations=function_declarations)]
        model = self._get_model(
            system_instruction=system_instruction,
            model_name=model_name,
            tools=tools,
        )
        generation_config = {"temperature": temperature}
        if max_tokens:
            generation_config["max_output_tokens"] = max_tokens
        try:
            response = model.generate_content(prompt, generation_config=generation_config)
        except google_exceptions.GoogleAPIError as e:
            logger.error(f"Google API error in generate_with_tools: {e}", exc_info=True)
            _raise_gemini_error(
                from_google_api_error(e),
                context="GeminiService.generate_with_tools",
            )
        # Parse: function_call in parts or text
        if not response.candidates:
            return {"text": ""}
        content = response.candidates[0].content
        if not hasattr(content, "parts") or not content.parts:
            return {"text": getattr(response, "text", "") or ""}
        text_parts = []
        for part in content.parts:
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                name = getattr(fc, "name", None) or (fc.get("name") if isinstance(fc, dict) else None)
                args = getattr(fc, "args", None)
                if not isinstance(args, dict):
                    try:
                        args = dict(args) if args and hasattr(args, "items") else {}
                    except (TypeError, ValueError):
                        args = {}
                args = args or {}
                if name:
                    return {"function_call": {"name": name, "args": args}}
            if hasattr(part, "text") and part.text:
                text_parts.append(part.text)
        return {"text": "\n".join(text_parts).strip() if text_parts else ""}

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
