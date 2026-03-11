"""
GeminiImageService - Service for generating images using Google Vertex AI Imagen API

This service provides image generation capabilities using Vertex AI's Imagen models.
It follows the same pattern as GeminiService for consistency.

Usage:
    from ai.gemini_image_service import GeminiImageService
    
    service = GeminiImageService()
    
    # Generate an image
    result = service.generate_image(
        prompt="A beautiful sunset over mountains",
        number_of_images=1,
        aspect_ratio="1:1"
    )
    
    # Save the image
    image_bytes = result['images'][0]
    with open('generated_image.png', 'wb') as f:
        f.write(image_bytes)

Nano Banana (Gemini image) — explainer images with text:
    service.generate_image_nano_banana(
        prompt="Create an explainer image: the water cycle with labels.",
        model_id="gemini-2.5-flash-image",
    )
    # Returns same shape: result['images'], result['model']; prints confirm model used.

Direct Testing:
    Run this file directly to test:
    python -m ai.gemini_image_service
    
    Or from Django shell:
    from ai.gemini_image_service import GeminiImageService
    service = GeminiImageService()
    service.test()
"""
import logging
import os
from typing import Dict, List, Optional, Any, Union
from google.cloud import aiplatform
from google.oauth2 import service_account
from vertexai.preview.vision_models import ImageGenerationModel
from google.api_core import exceptions as google_exceptions
from decouple import config

logger = logging.getLogger(__name__)


class GeminiImageService:
    """
    Service for generating images using Google Vertex AI Imagen API.
    
    This service provides a simple interface for generating images with:
    - Text-to-image generation
    - Configurable aspect ratios
    - Multiple image generation
    - Safety settings
    
    Note: imagegeneration@006 is end-of-life. Default is imagen-3.0-generate-002 (Imagen 3).
    This service uses ImageGenerationModel, which supports Imagen only. Gemini 2.5 Flash Image
    (gemini-2.5-flash-image / "Nano Banana") uses a different API (GenerativeModel); if you set
    IMAGEN_MODEL to that, we fall back to imagen-3.0-generate-002 and log a warning.
    
    Designed to follow the same pattern as GeminiService for consistency.
    """
    
    def __init__(self):
        """
        Initialize Vertex AI client for image generation.
        
        Reads configuration from environment variables:
        - GCP_PROJECT_ID: Google Cloud project ID
        - VERTEX_AI_LOCATION: Region (default: us-central1)
        - IMAGEN_MODEL: Imagen model only (default: imagen-3.0-generate-002). Gemini image models not supported here.
        - GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON (optional)
        """
        self.project_id = config('GCP_PROJECT_ID', default=None)
        self.location = config('VERTEX_AI_LOCATION', default='us-central1')
        # imagegeneration@006 is EOL. ImageGenerationModel supports Imagen only (not Gemini image models).
        # Options: imagen-3.0-generate-002, imagen-3.0-fast-generate-001, imagen-4.0-generate-001
        _requested = config('IMAGEN_MODEL', default='imagen-3.0-generate-002')
        if _requested and 'gemini' in _requested.lower():
            logger.warning(
                "IMAGEN_MODEL=%s uses a different API (GenerativeModel). This service uses "
                "ImageGenerationModel (Imagen only). Falling back to imagen-3.0-generate-002.",
                _requested,
            )
            self.model_name = 'imagen-3.0-generate-002'
        else:
            self.model_name = _requested or 'imagen-3.0-generate-002'
        
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
    
    def generate_image(
        self,
        prompt: str,
        number_of_images: int = 1,
        aspect_ratio: str = "1:1",
        negative_prompt: Optional[str] = None,
        safety_filter_level: str = "block_some",
        person_generation: str = "dont_allow",
        seed: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate image(s) from a text prompt using Imagen API.
        
        Args:
            prompt: Text description of the image to generate (required)
            number_of_images: Number of images to generate (1-4, default: 1)
            aspect_ratio: Aspect ratio for the image. Options:
                - "1:1" (square)
                - "9:16" (portrait)
                - "16:9" (landscape - widest supported)
                - "4:3" (standard)
                - "3:4" (portrait standard)
                Default: "1:1"
                
            Note: 3:1 is not supported by Imagen API. Use 16:9 for wide landscape images.
            negative_prompt: Optional text describing what to avoid in the image
            safety_filter_level: Safety filter level. Options:
                - "block_most" (strictest)
                - "block_some" (default)
                - "block_few"
                - "block_fewest"
            person_generation: Person generation setting. Options:
                - "dont_allow" (default, no people)
                - "allow_adult"
                - "allow_all"
            seed: Optional random seed for reproducible results
            **kwargs: Additional generation parameters
            
        Returns:
            Dictionary with:
            - 'images': List of image bytes (PNG format)
            - 'prompt': The prompt used
            - 'model': Model name used
            - 'number_of_images': Number of images generated
            - 'aspect_ratio': Aspect ratio used
            
        Raises:
            ValueError: If required parameters are missing or invalid
            Exception: If API call fails
        """
        if not prompt:
            raise ValueError("prompt is required")
        
        if number_of_images < 1 or number_of_images > 4:
            raise ValueError("number_of_images must be between 1 and 4")
        
        valid_aspect_ratios = ["1:1", "9:16", "16:9", "4:3", "3:4"]
        if aspect_ratio not in valid_aspect_ratios:
            raise ValueError(f"aspect_ratio must be one of: {', '.join(valid_aspect_ratios)}")
        
        try:
            # Initialize the model
            model = ImageGenerationModel.from_pretrained(self.model_name)
            
            logger.debug(f"Generating image with model: {self.model_name}")
            logger.debug(f"Prompt: {prompt[:100]}...")
            logger.debug(f"Number of images: {number_of_images}, Aspect ratio: {aspect_ratio}")
            
            # Build generation parameters
            generation_params = {
                "number_of_images": number_of_images,
                "aspect_ratio": aspect_ratio,
            }
            
            # Add optional parameters
            if negative_prompt:
                generation_params["negative_prompt"] = negative_prompt
                logger.debug(f"Negative prompt: {negative_prompt[:100]}...")
            
            if safety_filter_level:
                generation_params["safety_filter_level"] = safety_filter_level
            
            if person_generation:
                generation_params["person_generation"] = person_generation
            
            if seed is not None:
                generation_params["seed"] = seed
            
            # Add any additional kwargs
            generation_params.update(kwargs)
            
            # Generate images
            response = model.generate_images(
                prompt=prompt,
                **generation_params
            )
            
            # Extract image data
            images = []
            for image in response.images:
                # Get image bytes
                image_bytes = image._image_bytes
                images.append(image_bytes)
            
            logger.info(f"Successfully generated {len(images)} image(s)")
            
            return {
                'images': images,
                'prompt': prompt,
                'model': self.model_name,
                'number_of_images': len(images),
                'aspect_ratio': aspect_ratio,
                'negative_prompt': negative_prompt,
                'safety_filter_level': safety_filter_level,
                'person_generation': person_generation,
            }
            
        except google_exceptions.GoogleAPIError as e:
            logger.error(f"Google API error: {e}", exc_info=True)
            raise Exception(f"Imagen API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in generate_image: {e}", exc_info=True)
            raise
    
    def generate_image_nano_banana(
        self,
        prompt: str,
        model_id: str = "gemini-2.5-flash-image",
        aspect_ratio: str = "16:9",
    ) -> Dict[str, Any]:
        """
        Generate an image using Nano Banana (Gemini image model) via Vertex AI.
        Best for explainer images with text, labels, and structured layouts.

        Requires: pip install google-genai
        Env for Vertex: GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GOOGLE_GENAI_USE_VERTEXAI=True
        (project and location are taken from GCP_PROJECT_ID and VERTEX_AI_LOCATION if not set.)

        Args:
            prompt: Text description of the image (e.g. explainer with labels).
            model_id: Gemini image model. Options: gemini-2.5-flash-image, gemini-3.1-flash-image-preview.
            aspect_ratio: e.g. "16:9", "1:1". Passed to API when supported.

        Returns:
            Dict with 'images' (list of bytes), 'prompt', 'model', 'text_parts' (any text from the model).
        """
        print(f"[Nano Banana] Using model: {model_id}")
        try:
            from google import genai
            from google.genai.types import GenerateContentConfig, Modality
        except ImportError:
            raise ImportError(
                "google-genai is required for Nano Banana. Install with: pip install google-genai"
            )

        # Ensure Vertex AI env vars for google-genai SDK
        os.environ["GOOGLE_CLOUD_PROJECT"] = os.environ.get("GOOGLE_CLOUD_PROJECT") or self.project_id or ""
        os.environ["GOOGLE_CLOUD_LOCATION"] = os.environ.get("GOOGLE_CLOUD_LOCATION") or self.location or "us-central1"
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

        if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
            raise ValueError("GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT must be set for Nano Banana")

        # Use same service account as Imagen so genai client can auth to Vertex
        creds_path = config("GOOGLE_APPLICATION_CREDENTIALS", default=None)
        if not creds_path:
            try:
                from django.conf import settings
                base_dir = settings.BASE_DIR
            except Exception:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            default_creds = os.path.join(base_dir, ".credentials", "vertex-ai-service-account.json")
            if os.path.exists(default_creds):
                creds_path = default_creds
        if creds_path and os.path.exists(creds_path):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path

        client = genai.Client()
        config_kw = {"response_modalities": [Modality.TEXT, Modality.IMAGE]}
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=GenerateContentConfig(**config_kw),
        )

        images = []
        text_parts = []
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if getattr(part, "text", None):
                    text_parts.append(part.text)
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    images.append(bytes(part.inline_data.data))

        print(f"[Nano Banana] Model used: {model_id} — generated {len(images)} image(s)")
        return {
            "images": images,
            "prompt": prompt,
            "model": model_id,
            "text_parts": text_parts,
        }

    def save_image(self, image_bytes: bytes, filepath: str) -> str:
        """
        Save image bytes to a file.
        
        Args:
            image_bytes: Image data as bytes
            filepath: Path where to save the image
            
        Returns:
            The filepath where the image was saved
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
            
            with open(filepath, 'wb') as f:
                f.write(image_bytes)
            
            logger.info(f"Image saved to: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save image to {filepath}: {e}", exc_info=True)
            raise
    
    def test(self, test_prompt: Optional[str] = None, save_test_image: bool = False):
        """
        Direct test function for the service.
        
        Can be called directly to test the service:
        - From command line: python -m ai.gemini_image_service
        - From Django shell: GeminiImageService().test()
        
        Args:
            test_prompt: Optional custom test prompt, defaults to simple test
            save_test_image: Whether to save the generated test image to disk
        """
        print("\n" + "="*60)
        print("🧪 Testing GeminiImageService")
        print("="*60)
        
        if not self.project_id:
            print("❌ GCP_PROJECT_ID not set!")
            print("   Set it in your .env file or environment variables")
            return
        
        print(f"✅ Project ID: {self.project_id}")
        print(f"✅ Location: {self.location}")
        print(f"✅ Model: {self.model_name}")
        print()
        
        # Single image generation test
        print("Image Generation Test")
        print("-" * 60)
        try:
            prompt = test_prompt or "Picture a pencil in the middle of two books. One book is on the left, and the other book is on the right. The pencil is exactly in the middle. white background"
            result = self.generate_image(
                prompt=prompt,
                number_of_images=1,
                aspect_ratio="9:16"  # Widest landscape ratio supported by Imagen API
            )
            print(f"✅ Success!")
            print(f"Generated {result['number_of_images']} image(s)")
            print(f"Image size: {len(result['images'][0])} bytes")
            print(f"Aspect ratio: {result['aspect_ratio']}")
            print(f"Prompt: {prompt[:80]}...")
            
            if save_test_image:
                test_filepath = "test_generated_image.png"
                self.save_image(result['images'][0], test_filepath)
                print(f"✅ Image saved to: {test_filepath}")
            print()
        except Exception as e:
            print(f"❌ Failed: {e}")
            import traceback
            traceback.print_exc()
            print()

        # Nano Banana (Gemini image) test — explainer with text
        print("Nano Banana (Gemini image) Test")
        print("-" * 60)
        try:
            nano_prompt = (
                "Create an explainer image for kids: the water cycle. "
                "Show evaporation, condensation, and precipitation with short labels on the diagram. "
                "Clear, educational style."
            )
            print(f"Prompt: {nano_prompt[:80]}...")
            nano_result = self.generate_image_nano_banana(
                prompt=nano_prompt,
                model_id="gemini-2.5-flash-image",
                aspect_ratio="16:9",
            )
            print(f"✅ Nano Banana success!")
            print(f"Model used: {nano_result['model']}")
            print(f"Generated {len(nano_result['images'])} image(s)")
            if nano_result.get("text_parts"):
                print(f"Model text: {nano_result['text_parts'][0][:200]}...")
            if nano_result["images"]:
                print(f"Image size: {len(nano_result['images'][0])} bytes")
                if save_test_image:
                    nano_path = "test_nano_banana_image.png"
                    self.save_image(nano_result["images"][0], nano_path)
                    print(f"✅ Image saved to: {nano_path}")
            print()
        except ImportError as e:
            print(f"⚠️ Skipping Nano Banana (install google-genai): {e}")
            print()
        except Exception as e:
            print(f"❌ Nano Banana failed: {e}")
            import traceback
            traceback.print_exc()
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
    service = GeminiImageService()
    
    # Run tests
    service.test(save_test_image=True)

