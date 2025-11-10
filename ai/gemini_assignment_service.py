"""
GeminiAssignmentService - Service for generating assignments using Gemini AI

This service extends GeminiService to provide assignment generation functionality.
It accepts only text content (no video URLs or YouTube handling).
All content extraction and transcription should be handled by the calling view.

Usage:
    from ai.gemini_assignment_service import GeminiAssignmentService
    
    service = GeminiAssignmentService()
    
    result = service.generate(
        system_instruction="You are an expert assignment creator...",
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
    from .schemas import get_assignment_generation_schema
except ImportError:
    # If running as script, add parent directory to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ai.gemini_service import GeminiService
    from ai.schemas import get_assignment_generation_schema

logger = logging.getLogger(__name__)


class GeminiAssignmentService:
    """
    Service for generating assignments using Gemini AI.
    
    Extends GeminiService to provide assignment-specific functionality.
    Accepts only text content - all content extraction/transcription handled by views.
    """
    
    def __init__(self):
        """Initialize the service with base GeminiService"""
        self.gemini_service = GeminiService()
        logger.info("GeminiAssignmentService initialized")
    
    def generate(
        self,
        system_instruction: str,
        lesson_title: str,
        lesson_description: str,
        content: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        total_questions: int = 5,
        essay_count: int = 2,
        fill_blank_count: int = 3
    ) -> Dict[str, Any]:
        """
        Generate assignment using Gemini AI.
        
        Args:
            system_instruction: System instruction/prompt from frontend
            lesson_title: Title of the lesson
            lesson_description: Description of the lesson
            content: Combined text content from all selected materials (required)
            temperature: Temperature for generation (0.0-1.0, default: 0.7)
            max_tokens: Maximum tokens in response (optional)
            
        Returns:
            Dictionary containing generated assignment data:
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
            if essay_count + fill_blank_count != total_questions:
                # Auto-adjust to match total
                if essay_count + fill_blank_count > total_questions:
                    # Reduce proportionally
                    ratio = total_questions / (essay_count + fill_blank_count)
                    essay_count = int(essay_count * ratio)
                    fill_blank_count = total_questions - essay_count
                else:
                    # Increase to match total
                    fill_blank_count = total_questions - essay_count
            
            # Build prompt with lesson info, content, and question requirements
            # Handle optional lesson_description gracefully
            lesson_desc_section = f"Lesson Description: {lesson_description}\n" if lesson_description else ""
            prompt = f"""Generate a comprehensive assignment for the following lesson:

Lesson Title: {lesson_title}
{lesson_desc_section}

Content:
{content}

Generate exactly {total_questions} assignment questions that require students to demonstrate understanding and application of the lesson content:
- Exactly {essay_count} essay questions
- Exactly {fill_blank_count} fill-in-the-blank questions

Each question should have clear requirements and helpful explanations. Essay questions should include grading rubrics or criteria. Fill-in-the-blank questions should test key concepts from the material."""
            
            # Get schema for structured output
            response_schema = get_assignment_generation_schema()
            
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
                'title': parsed_data.get('title', f'Assignment: {lesson_title}'),
                'description': parsed_data.get('description', ''),
                'questions': parsed_data.get('questions', [])
            }
            
            # Ensure questions have correct structure
            validated_questions = []
            for q in result['questions']:
                validated_q = {
                    'question_text': q.get('question_text', ''),
                    'type': q.get('type', 'essay'),
                    'points': q.get('points', 10),
                    'content': q.get('content', {}),
                    'explanation': q.get('explanation', '')
                }
                
                # Validate content based on question type
                if validated_q['type'] == 'fill_blank':
                    if 'blanks' not in validated_q['content']:
                        validated_q['content']['blanks'] = []
                    if 'correct_answers' not in validated_q['content']:
                        validated_q['content']['correct_answers'] = {}
                elif validated_q['type'] == 'essay':
                    if 'rubric' not in validated_q['content']:
                        validated_q['content']['rubric'] = ''
                    if 'instructions' not in validated_q['content']:
                        validated_q['content']['instructions'] = ''
                elif validated_q['type'] == 'short_answer':
                    if 'correct_answer' not in validated_q['content']:
                        validated_q['content']['correct_answer'] = ''
                    if 'accept_variations' not in validated_q['content']:
                        validated_q['content']['accept_variations'] = True
                
                validated_questions.append(validated_q)
            
            result['questions'] = validated_questions
            
            logger.info(f"Successfully generated assignment with {len(result['questions'])} questions for: {lesson_title}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating assignment: {e}", exc_info=True)
            raise
    
    def test(self):
        """
        Test function for the assignment service.
        
        Can be called directly:
        - From Django shell: GeminiAssignmentService().test()
        - From command line: python -m ai.gemini_assignment_service
        """
        print("\n" + "="*60)
        print("🧪 Testing GeminiAssignmentService")
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
        print("📝 Testing assignment generation with sample lesson content...")
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
                system_instruction="""You are an expert assignment creator specializing in educational content.
Generate comprehensive assignment questions that require students to demonstrate understanding and application of lesson material.
Create a mix of essay questions, fill-in-the-blank, and short answer questions with clear requirements.""",
                lesson_title="Introduction to Python Programming",
                lesson_description="Learn the basics of Python programming including variables, data types, and basic operations.",
                content=combined_content,
                temperature=0.7
            )
            
            print("✅ Assignment generated successfully!")
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
                if q['type'] == 'fill_blank' and 'blanks' in q['content']:
                    print(f"   Blanks: {q['content']['blanks']}")
                if q['type'] == 'essay' and 'rubric' in q['content']:
                    print(f"   Rubric: {q['content']['rubric']}")
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
    service = GeminiAssignmentService()
    service.test()

