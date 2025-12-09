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
    
    Note: Uses Imagen 3 (imagegeneration@006) by default. "Nano Banana" (Gemini 2.5 Flash Image)
    and "Nano Banana Pro" (Gemini 3.0 Pro Image) are consumer-facing names that use
    Imagen technology. For Vertex AI, use imagegeneration@006 or check for newer versions.
    
    Designed to follow the same pattern as GeminiService for consistency.
    """
    
    def __init__(self):
        """
        Initialize Vertex AI client for image generation.
        
        Reads configuration from environment variables:
        - GCP_PROJECT_ID: Google Cloud project ID
        - VERTEX_AI_LOCATION: Region (default: us-central1)
        - IMAGEN_MODEL: Model name (default: imagegeneration@006)
        - GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON (optional)
        """
        self.project_id = config('GCP_PROJECT_ID', default=None)
        self.location = config('VERTEX_AI_LOCATION', default='us-central1')
        # Imagen 3 model: imagegeneration@006 (latest as of 2025)
        # Note: "Nano Banana" (Gemini 2.5 Flash Image) and "Nano Banana Pro" (Gemini 3.0 Pro Image)
        # are consumer-facing names that may use Imagen technology under the hood.
        # For Vertex AI, use imagegeneration@006 or check for newer versions (e.g., imagegeneration@007)
        # Older models: imagegeneration@005, imagegeneration@004
        self.model_name = config('IMAGEN_MODEL', default='imagegeneration@006')
        
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
                aspect_ratio="16:9"  # Widest landscape ratio supported by Imagen API
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

