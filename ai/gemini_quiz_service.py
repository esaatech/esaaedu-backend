"""
GeminiQuizService - Service for generating quizzes using Gemini AI

This service extends GeminiService to provide quiz generation functionality.
It accepts lesson content, materials content, and video URLs (including YouTube)
to generate comprehensive quiz questions.

Usage:
    from ai.gemini_quiz_service import GeminiQuizService
    
    service = GeminiQuizService()
    
    result = service.generate(
        system_instruction="You are an expert quiz creator...",
        lesson_title="Introduction to Python",
        lesson_description="Learn Python basics",
        lesson_content="Python is a programming language...",
        materials_content=["Note 1 content", "Note 2 content"],
        video_url="https://www.youtube.com/watch?v=...",
        temperature=0.7
    )
"""
import logging
import re
import sys
import os
from typing import Dict, Any, Optional, List

# Handle both module import and direct execution
try:
    from .gemini_service import GeminiService
    from .schemas import get_quiz_generation_schema
except ImportError:
    # If running as script, add parent directory to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ai.gemini_service import GeminiService
    from ai.schemas import get_quiz_generation_schema

logger = logging.getLogger(__name__)


class GeminiQuizService:
    """
    Service for generating quizzes using Gemini AI.
    
    Extends GeminiService to provide quiz-specific functionality.
    Supports multiple content sources: lesson content, materials, and YouTube videos.
    """
    
    def __init__(self):
        """Initialize the service with base GeminiService"""
        self.gemini_service = GeminiService()
        logger.info("GeminiQuizService initialized")
    
    def _is_youtube_url(self, url: str) -> bool:
        """Check if URL is a YouTube URL"""
        if not url:
            return False
        youtube_patterns = [
            r'youtube\.com/watch\?v=',
            r'youtu\.be/',
            r'youtube\.com/embed/',
            r'youtube\.com/v/'
        ]
        return any(re.search(pattern, url) for pattern in youtube_patterns)
    
    def _extract_youtube_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL"""
        if not url:
            return None
        
        patterns = [
            r'youtube\.com/watch\?v=([^&]+)',
            r'youtu\.be/([^?]+)',
            r'youtube\.com/embed/([^?]+)',
            r'youtube\.com/v/([^?]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def generate(
        self,
        system_instruction: str,
        lesson_title: str,
        lesson_description: str,
        lesson_content: Optional[str] = None,
        materials_content: Optional[List[str]] = None,
        video_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate quiz using Gemini AI.
        
        Args:
            system_instruction: System instruction/prompt from frontend
            lesson_title: Title of the lesson
            lesson_description: Description of the lesson
            lesson_content: Text content of the lesson (optional)
            materials_content: List of material content strings (optional)
            video_url: YouTube or video URL (optional)
            temperature: Temperature for generation (0.0-1.0, default: 0.7)
            max_tokens: Maximum tokens in response (optional)
            
        Returns:
            Dictionary containing generated quiz data:
            {
                'title': str,
                'description': str,
                'questions': List[Dict]  # Each question has question_text, type, points, content, explanation
            }
            
        Raises:
            ValueError: If required parameters are missing
            Exception: If API call fails
        """
        if not system_instruction:
            raise ValueError("system_instruction is required")
        if not lesson_title:
            raise ValueError("lesson_title is required")
        if not lesson_description:
            raise ValueError("lesson_description is required")
        
        try:
            # Build comprehensive prompt with all available content
            prompt_parts = [
                f"Generate a comprehensive quiz for the following lesson:",
                f"",
                f"Lesson Title: {lesson_title}",
                f"Lesson Description: {lesson_description}"
            ]
            
            # Add lesson content if available
            if lesson_content and lesson_content.strip():
                prompt_parts.append("")
                prompt_parts.append("Lesson Content:")
                prompt_parts.append(lesson_content)
            
            # Add materials content if available
            if materials_content:
                materials_text = "\n\n".join([
                    f"Material {i+1}:\n{content}" 
                    for i, content in enumerate(materials_content) 
                    if content and content.strip()
                ])
                if materials_text:
                    prompt_parts.append("")
                    prompt_parts.append("Additional Materials:")
                    prompt_parts.append(materials_text)
            
            # Add video URL information if available
            if video_url:
                if self._is_youtube_url(video_url):
                    youtube_id = self._extract_youtube_id(video_url)
                    prompt_parts.append("")
                    prompt_parts.append(f"Video Content: YouTube video (ID: {youtube_id})")
                    prompt_parts.append(f"Video URL: {video_url}")
                    prompt_parts.append("")
                    prompt_parts.append("Please analyze the video content and generate quiz questions based on it.")
                else:
                    prompt_parts.append("")
                    prompt_parts.append(f"Video Content: {video_url}")
            
            prompt_parts.append("")
            prompt_parts.append("Generate quiz questions that test understanding of the lesson content. Include a mix of multiple choice and true/false questions. Each question should have clear correct answers and helpful explanations.")
            
            prompt = "\n".join(prompt_parts)
            
            # Get schema for structured output
            response_schema = get_quiz_generation_schema()
            
            # Prepare content parts for multi-modal input (if video URL provided)
            content_parts = []
            
            # Add text prompt
            content_parts.append(prompt)
            
            # Add video if YouTube URL is provided
            if video_url and self._is_youtube_url(video_url):
                try:
                    from vertexai.generative_models import Part
                    # Create video part from YouTube URL
                    video_part = Part.from_uri(
                        uri=video_url,
                        mime_type="video/*"
                    )
                    content_parts.append(video_part)
                    logger.info(f"Added YouTube video to content: {video_url}")
                except Exception as e:
                    logger.warning(f"Failed to add video part, will use text-only: {e}")
                    # Continue with text-only if video fails
            
            # Call base service with multi-modal content if video provided
            if len(content_parts) > 1:
                # Multi-modal input (text + video)
                response = self._generate_with_multimodal(
                    system_instruction=system_instruction,
                    content_parts=content_parts,
                    response_schema=response_schema,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            else:
                # Text-only input
                response = self.gemini_service.generate(
                    system_instruction=system_instruction,
                    prompt=prompt,
                    response_schema=response_schema,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            
            # Extract parsed data
            if not response.get('parsed'):
                raise ValueError("Failed to parse AI response")
            
            parsed_data = response['parsed']
            
            # Validate and structure result
            result = {
                'title': parsed_data.get('title', f'Quiz: {lesson_title}'),
                'description': parsed_data.get('description', ''),
                'questions': parsed_data.get('questions', [])
            }
            
            # Ensure questions have correct structure
            validated_questions = []
            for q in result['questions']:
                validated_q = {
                    'question_text': q.get('question_text', ''),
                    'type': q.get('type', 'multiple_choice'),
                    'points': q.get('points', 1),
                    'content': q.get('content', {}),
                    'explanation': q.get('explanation', '')
                }
                
                # Validate content based on question type
                if validated_q['type'] == 'multiple_choice':
                    if 'options' not in validated_q['content']:
                        validated_q['content']['options'] = []
                    if 'correct_answer' not in validated_q['content']:
                        validated_q['content']['correct_answer'] = ''
                elif validated_q['type'] == 'true_false':
                    if 'correct_answer' not in validated_q['content']:
                        validated_q['content']['correct_answer'] = 'true'
                
                validated_questions.append(validated_q)
            
            result['questions'] = validated_questions
            
            logger.info(f"Successfully generated quiz with {len(result['questions'])} questions for: {lesson_title}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating quiz: {e}", exc_info=True)
            raise
    
    def _generate_with_multimodal(
        self,
        system_instruction: str,
        content_parts: List[Any],
        response_schema: Dict[str, Any],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate content with multi-modal input (text + video).
        
        This method handles the case where we have both text and video content.
        """
        import json
        from vertexai.generative_models import GenerativeModel
        from google.api_core import exceptions as google_exceptions
        
        try:
            # Get model with system instruction
            model = self.gemini_service._get_model(system_instruction=system_instruction)
            
            # Build generation config
            generation_config = {
                'temperature': temperature,
            }
            
            if max_tokens:
                generation_config['max_output_tokens'] = max_tokens
            
            # Add schema instruction to text prompt (first part)
            if response_schema and len(content_parts) > 0:
                schema_json = json.dumps(response_schema, indent=2)
                text_prompt = content_parts[0]
                content_parts[0] = f"""{text_prompt}

IMPORTANT: Please respond with valid JSON matching this schema:
{schema_json}

Return ONLY valid JSON, no additional text before or after."""
            
            # Generate content with multi-modal input
            logger.debug(f"Generating content with multi-modal input (text + video)")
            response = model.generate_content(
                content_parts,
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
                'model': self.gemini_service.model_name
            }
            
        except google_exceptions.GoogleAPIError as e:
            logger.error(f"Google API error: {e}", exc_info=True)
            raise Exception(f"Gemini API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in multi-modal generation: {e}", exc_info=True)
            raise
    
    def test(self):
        """
        Test function for the quiz service.
        
        Can be called directly:
        - From Django shell: GeminiQuizService().test()
        - From command line: python -m ai.gemini_quiz_service
        """
        print("\n" + "="*60)
        print("🧪 Testing GeminiQuizService")
        print("="*60)
        
        if not self.gemini_service.project_id:
            print("❌ GCP_PROJECT_ID not set!")
            print("   Set it in your .env file or environment variables")
            return
        
        print(f"✅ Project ID: {self.gemini_service.project_id}")
        print(f"✅ Location: {self.gemini_service.location}")
        print(f"✅ Model: {self.gemini_service.model_name}")
        print()
        
        # Test with sample data
        print("📝 Testing quiz generation with sample lesson content...")
        print()
        
        try:
            result = self.generate(
                system_instruction="""You are an expert quiz creator specializing in educational content.
Generate comprehensive quiz questions that test understanding of the lesson material.
Create a mix of multiple choice and true/false questions with clear correct answers.""",
                lesson_title="Introduction to Python Programming",
                lesson_description="Learn the basics of Python programming including variables, data types, and basic operations.",
                lesson_content="""Python is a high-level programming language known for its simplicity and readability.

Key Concepts:
1. Variables: Store data values (e.g., x = 5)
2. Data Types: Integers, floats, strings, booleans
3. Basic Operations: Arithmetic (+, -, *, /), comparison (==, !=, <, >)
4. Print Function: Display output (print('Hello World'))

Python uses indentation to define code blocks, making it easy to read.""",
                materials_content=[
                    "Python was created by Guido van Rossum in 1991.",
                    "Python is an interpreted language, meaning code is executed line by line."
                ],
                temperature=0.7
            )
            
            print("✅ Quiz generated successfully!")
            print()
            print(f"Title: {result['title']}")
            print(f"Description: {result['description']}")
            print(f"Number of questions: {len(result['questions'])}")
            print()
            print("Questions:")
            for i, q in enumerate(result['questions'], 1):
                print(f"\n{i}. {q['question_text']}")
                print(f"   Type: {q['type']}")
                print(f"   Points: {q['points']}")
                if q['type'] == 'multiple_choice' and 'options' in q['content']:
                    print(f"   Options: {q['content']['options']}")
                if 'correct_answer' in q['content']:
                    print(f"   Correct Answer: {q['content']['correct_answer']}")
                if q.get('explanation'):
                    print(f"   Explanation: {q['explanation']}")
            
            print()
            print("="*60)
            print("✅ Test completed successfully!")
            print("="*60)
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            print()
            print("="*60)
            print("❌ Test failed")
            print("="*60)


if __name__ == "__main__":
    # Allow running as a script for testing
    import os
    import django
    import sys
    
    # Get the backend directory (parent of 'ai' directory)
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Add backend directory to Python path BEFORE Django setup
    # This ensures Django can find the 'backend' module
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    
    # Setup Django environment
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    django.setup()
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run test
    service = GeminiQuizService()
    service.test()

