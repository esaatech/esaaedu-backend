"""
GeminiCourseLessonsService - Service for generating course lessons using Gemini AI

This service extends GeminiService to provide lesson generation functionality.
It accepts system_instruction from the frontend for flexibility.

Usage:
    from ai.gemini_course_lessons_service import GeminiCourseLessonsService
    
    service = GeminiCourseLessonsService()
    
    result = service.generate(
        system_instruction="You are an expert curriculum designer...",
        course_title="Introduction to Python",
        course_description="Learn Python programming basics",
        duration_weeks=8,
        sessions_per_week=2,
        temperature=0.7
    )
"""
import logging
from typing import Dict, Any, Optional, List
from .gemini_service import GeminiService
from .schemas import get_lesson_generation_schema

logger = logging.getLogger(__name__)


class GeminiCourseLessonsService:
    """
    Service for generating course lessons using Gemini AI.
    
    Extends GeminiService to provide lesson generation-specific functionality.
    Accepts system_instruction from frontend for flexibility.
    """
    
    def __init__(self):
        """Initialize the service with base GeminiService"""
        self.gemini_service = GeminiService()
        logger.info("GeminiCourseLessonsService initialized")
    
    def generate(
        self,
        system_instruction: str,
        course_title: str,
        course_description: str,
        duration_weeks: Optional[int] = None,
        sessions_per_week: Optional[int] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate course lessons using Gemini AI.
        
        Args:
            system_instruction: System instruction/prompt from frontend
            course_title: Title of the course
            course_description: Description of the course
            duration_weeks: Number of weeks the course runs (optional)
            sessions_per_week: Number of sessions per week (optional)
            temperature: Temperature for generation (0.0-1.0, default: 0.7)
            max_tokens: Maximum tokens in response (optional)
            
        Returns:
            Dictionary containing generated lessons data:
            {
                'lessons': [
                    {
                        'title': str,
                        'description': str,
                        'order': int,
                        'type': str ('live_class', 'video_audio', 'text_lesson'),
                        'duration': int (minutes)
                    },
                    ...
                ]
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
            
            prompt_parts = [
                f"Generate lesson outlines for the following course:",
                f"Course Title: {course_title}",
                f"Course Description: {description_text}"
            ]
            
            if duration_weeks:
                prompt_parts.append(f"Duration: {duration_weeks} weeks")
            if sessions_per_week:
                prompt_parts.append(f"Sessions per week: {sessions_per_week}")
            
            prompt_parts.append("\nPlease generate a comprehensive list of lessons organized in a cumulative/scaffolded order. Each lesson should have a title, description, order number, type (default: live_class), and duration in minutes (default: 45).")
            
            prompt = "\n".join(prompt_parts)
            
            # Get schema for structured output
            response_schema = get_lesson_generation_schema()
            
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
            
            # Validate and ensure lessons array exists
            lessons = parsed_data.get('lessons', [])
            
            # Ensure all lessons have required fields and defaults
            validated_lessons = []
            for lesson in lessons:
                validated_lesson = {
                    'title': lesson.get('title', 'Untitled Lesson'),
                    'description': lesson.get('description', ''),
                    'order': lesson.get('order', len(validated_lessons) + 1),
                    'type': lesson.get('type', 'live_class'),
                    'duration': lesson.get('duration', 45)
                }
                validated_lessons.append(validated_lesson)
            
            # Sort by order to ensure correct sequence
            validated_lessons.sort(key=lambda x: x['order'])
            
            result = {
                'lessons': validated_lessons
            }
            
            logger.info(f"Successfully generated {len(validated_lessons)} lessons for course: {course_title}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating course lessons: {e}", exc_info=True)
            raise

