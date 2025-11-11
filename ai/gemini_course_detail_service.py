"""
GeminiCourseDetailService - Service for generating course details using Gemini AI

This service extends GeminiService to provide course detail generation functionality.
It generates basic course information: title, short description, detailed description, category, and difficulty level.

Usage:
    from ai.gemini_course_detail_service import GeminiCourseDetailService
    
    service = GeminiCourseDetailService()
    
    result = service.generate(
        system_instruction="You are an expert course creator...",
        user_request="Create a course on Python programming for beginners",
        temperature=0.7
    )
"""
import logging
from typing import Dict, Any, Optional
from .gemini_service import GeminiService
from .schemas import get_course_detail_schema

logger = logging.getLogger(__name__)


class GeminiCourseDetailService:
    """
    Service for generating course details using Gemini AI.
    
    Extends GeminiService to provide course detail-specific functionality.
    Accepts system_instruction from frontend for flexibility.
    """
    
    def __init__(self):
        """Initialize the service with base GeminiService"""
        self.gemini_service = GeminiService()
        logger.info("GeminiCourseDetailService initialized")
    
    def generate(
        self,
        system_instruction: str,
        user_request: str,
        persona: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate course details using Gemini AI.
        
        Args:
            system_instruction: System instruction/prompt from frontend (or from AIPromptTemplate)
            user_request: User's request describing the course they want to create
            persona: Optional persona/style for the course (e.g., "fun and engaging", "professional", "playful")
            temperature: Temperature for generation (0.0-1.0, default: 0.7)
            max_tokens: Maximum tokens in response (optional)
            
        Returns:
            Dictionary containing generated course detail data:
            {
                'title': str,
                'short_description': str,
                'detailed_description': str,
                'category': str,
                'difficulty_level': str  # 'beginner', 'intermediate', or 'advanced'
            }
            
        Raises:
            ValueError: If required parameters are missing
            Exception: If API call fails
        """
        if not system_instruction:
            raise ValueError("system_instruction is required")
        if not user_request or not user_request.strip():
            raise ValueError("user_request is required")
        
        try:
            # Build prompt with user request and persona
            prompt_parts = [
                f"Generate comprehensive course details based on the following request:",
                f"",
                f"{user_request}"
            ]
            
            if persona:
                prompt_parts.append(f"")
                prompt_parts.append(f"Course Persona/Style: {persona}")
            
            prompt_parts.extend([
                f"",
                f"Please generate:",
                f"- A clear and engaging course title",
                f"- A short description (1-2 sentences) that captures the essence of the course",
                f"- A detailed description (multiple paragraphs) that provides comprehensive information about what students will learn",
                f"- An appropriate category for the course",
                f"- The difficulty level (beginner, intermediate, or advanced) based on the course content",
                f"",
                f"Ensure all information is accurate, engaging, and appropriate for the target audience."
            ])
            
            prompt = "\n".join(prompt_parts)
            
            # Get schema for structured output
            response_schema = get_course_detail_schema()
            
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
            result = {
                'title': parsed_data.get('title', ''),
                'short_description': parsed_data.get('short_description', ''),
                'detailed_description': parsed_data.get('detailed_description', ''),
                'category': parsed_data.get('category', ''),
                'difficulty_level': parsed_data.get('difficulty_level', 'beginner')
            }
            
            # Validate difficulty_level is one of the allowed values
            if result['difficulty_level'] not in ['beginner', 'intermediate', 'advanced']:
                logger.warning(f"Invalid difficulty_level '{result['difficulty_level']}', defaulting to 'beginner'")
                result['difficulty_level'] = 'beginner'
            
            # Ensure all required fields are not empty
            if not result['title']:
                raise ValueError("Generated course title is empty")
            if not result['short_description']:
                raise ValueError("Generated short description is empty")
            if not result['detailed_description']:
                raise ValueError("Generated detailed description is empty")
            if not result['category']:
                raise ValueError("Generated category is empty")
            
            logger.info(f"Successfully generated course details: {result['title']}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating course details: {e}", exc_info=True)
            raise

