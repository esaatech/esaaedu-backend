"""
GeminiCourseIntroductionService - Service for generating course introductions using Gemini AI

This service extends GeminiService to provide course introduction generation functionality.
It accepts system_instruction from the frontend for flexibility.

Usage:
    from ai.gemini_course_introduction_service import GeminiCourseIntroductionService
    
    service = GeminiCourseIntroductionService()
    
    result = service.generate(
        system_instruction="You are an expert course creator...",
        course_title="Introduction to Python",
        course_description="Learn Python programming basics",
        temperature=0.7
    )
"""
import logging
from typing import Dict, Any, Optional
from .gemini_service import GeminiService
from .schemas import get_course_introduction_schema

logger = logging.getLogger(__name__)


class GeminiCourseIntroductionService:
    """
    Service for generating course introductions using Gemini AI.
    
    Extends GeminiService to provide course introduction-specific functionality.
    Accepts system_instruction from frontend for flexibility.
    """
    
    def __init__(self):
        """Initialize the service with base GeminiService"""
        self.gemini_service = GeminiService()
        logger.info("GeminiCourseIntroductionService initialized")
    
    def generate(
        self,
        system_instruction: str,
        course_title: str,
        course_description: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate course introduction using Gemini AI.
        
        Args:
            system_instruction: System instruction/prompt from frontend
            course_title: Title of the course
            course_description: Description of the course
            temperature: Temperature for generation (0.0-1.0, default: 0.7)
            max_tokens: Maximum tokens in response (optional)
            
        Returns:
            Dictionary containing generated course introduction data:
            {
                'overview': str,
                'learning_objectives': List[str],
                'prerequisites_text': List[str],
                'duration_weeks': int,
                'sessions_per_week': int,
                'total_projects': int,
                'max_students': int,
                'value_propositions': List[Dict[str, str]]
            }
            
        Raises:
            ValueError: If required parameters are missing
            Exception: If API call fails
        """
        if not system_instruction:
            raise ValueError("system_instruction is required")
        if not course_title:
            raise ValueError("course_title is required")
        if not course_description:
            raise ValueError("course_description is required")
        
        try:
            # Build prompt with course context
            # Use long_description if available, otherwise fall back to description
            description_text = course_description if course_description else "No description provided"
            
            prompt = f"""Generate a comprehensive course introduction for the following course:

Course Title: {course_title}
Course Description: {description_text}

IMPORTANT: Only generate the following fields:
- overview (required)
- learning_objectives (required)
- prerequisites_text (required)
- value_propositions (required)

DO NOT generate duration_weeks, sessions_per_week, total_projects, or max_students. These operational fields are managed separately and should not be included in the course introduction generation.

Use the detailed course description to create accurate and specific learning objectives and value propositions that reflect the actual course content."""
            
            # Get schema for structured output
            response_schema = get_course_introduction_schema()
            
            # Call base service
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
            
            # Validate and ensure all required fields are present
            # Note: duration_weeks, sessions_per_week, total_projects, and max_students are optional
            # Only include them if the AI explicitly generated them (not None)
            result = {
                'overview': parsed_data.get('overview', ''),
                'learning_objectives': parsed_data.get('learning_objectives', []),
                'prerequisites_text': parsed_data.get('prerequisites_text', []),
                'value_propositions': parsed_data.get('value_propositions', [])
            }
            
            # Only include operational fields if AI generated them (not None/undefined)
            # These fields should not be generated by default per the updated prompt
            if parsed_data.get('duration_weeks') is not None:
                result['duration_weeks'] = parsed_data.get('duration_weeks')
            if parsed_data.get('sessions_per_week') is not None:
                result['sessions_per_week'] = parsed_data.get('sessions_per_week')
            if parsed_data.get('total_projects') is not None:
                result['total_projects'] = parsed_data.get('total_projects')
            if parsed_data.get('max_students') is not None:
                result['max_students'] = parsed_data.get('max_students')
            
            # Ensure value_propositions have correct structure
            if result['value_propositions']:
                result['value_propositions'] = [
                    {
                        'title': vp.get('title', ''),
                        'description': vp.get('description', '')
                    }
                    for vp in result['value_propositions']
                ]
            
            logger.info(f"Successfully generated course introduction for: {course_title}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating course introduction: {e}", exc_info=True)
            raise

