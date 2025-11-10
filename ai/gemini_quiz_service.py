"""
GeminiQuizService - Service for generating quizzes using Gemini AI

This service extends GeminiService to provide quiz generation functionality.
It accepts only text content (no video URLs or YouTube handling).
All content extraction and transcription should be handled by the calling view.

Usage:
    from ai.gemini_quiz_service import GeminiQuizService
    
    service = GeminiQuizService()
    
    result = service.generate(
        system_instruction="You are an expert quiz creator...",
        lesson_title="Introduction to Python",
        lesson_description="Learn Python basics",
        content="Python is a programming language...",  # Combined text content
        temperature=0.7
    )
"""
import logging
import sys
import os
from typing import Dict, Any, Optional

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
    Accepts only text content - all content extraction/transcription handled by views.
    """
    
    def __init__(self):
        """Initialize the service with base GeminiService"""
        self.gemini_service = GeminiService()
        logger.info("GeminiQuizService initialized")
    
    def generate(
        self,
        system_instruction: str,
        lesson_title: str,
        lesson_description: str,
        content: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        total_questions: int = 10,
        multiple_choice_count: int = 7,
        true_false_count: int = 3
    ) -> Dict[str, Any]:
        """
        Generate quiz using Gemini AI.
        
        Args:
            system_instruction: System instruction/prompt from frontend
            lesson_title: Title of the lesson
            lesson_description: Description of the lesson
            content: Combined text content from all selected materials (required)
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
        # lesson_description is optional - can be empty string
        if not content or not content.strip():
            raise ValueError("content is required")
        
        try:
            # Validate question counts
            if multiple_choice_count + true_false_count != total_questions:
                # Auto-adjust to match total
                if multiple_choice_count + true_false_count > total_questions:
                    # Reduce proportionally
                    ratio = total_questions / (multiple_choice_count + true_false_count)
                    multiple_choice_count = int(multiple_choice_count * ratio)
                    true_false_count = total_questions - multiple_choice_count
                else:
                    # Increase to match total
                    true_false_count = total_questions - multiple_choice_count
            
            # Build prompt with lesson info, content, and question requirements
            # Handle optional lesson_description gracefully
            lesson_desc_section = f"Lesson Description: {lesson_description}\n" if lesson_description else ""
            prompt = f"""Generate a comprehensive quiz for the following lesson:

Lesson Title: {lesson_title}
{lesson_desc_section}

Content:
{content}

Generate exactly {total_questions} quiz questions that test understanding of the lesson content:
- Exactly {multiple_choice_count} multiple choice questions
- Exactly {true_false_count} true/false questions

Each question should have clear correct answers and helpful explanations. Ensure the questions cover different aspects of the lesson content."""
            
            # Get schema for structured output
            response_schema = get_quiz_generation_schema()
            
            # Call base service with text-only input
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
            # Combine content for test
            combined_content = """Python is a high-level programming language known for its simplicity and readability.

Key Concepts:
1. Variables: Store data values (e.g., x = 5)
2. Data Types: Integers, floats, strings, booleans
3. Basic Operations: Arithmetic (+, -, *, /), comparison (==, !=, <, >)
4. Print Function: Display output (print('Hello World'))

Python uses indentation to define code blocks, making it easy to read.

Additional Material:
Python was created by Guido van Rossum in 1991.
Python is an interpreted language, meaning code is executed line by line."""
            
            result = self.generate(
                system_instruction="""You are an expert quiz creator specializing in educational content.
Generate comprehensive quiz questions that test understanding of the lesson material.
Create a mix of multiple choice and true/false questions with clear correct answers.""",
                lesson_title="Introduction to Python Programming",
                lesson_description="Learn the basics of Python programming including variables, data types, and basic operations.",
                content=combined_content,
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

