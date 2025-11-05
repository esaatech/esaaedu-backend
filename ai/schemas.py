"""
Output schemas for structured AI responses
Separated from logic for reusability and maintainability
"""
from typing import Dict, Any


def get_course_generation_schema() -> Dict[str, Any]:
    """
    Schema for course generation structured output
    
    Returns:
        JSON Schema dict for course generation
    """
    return {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Course title"
            },
            "description": {
                "type": "string",
                "description": "Short course description"
            },
            "long_description": {
                "type": "string",
                "description": "Detailed course description"
            },
            "category": {
                "type": "string",
                "description": "Course category name"
            }
        },
        "required": ["title", "description"]
    }


def get_function_calling_schema() -> Dict[str, Any]:
    """
    Schema for function calling - defines what the AI can call
    This is used by Vertex AI's function calling feature
    
    Returns:
        Function declaration schema for course generation
    """
    return {
        "name": "generate_course",
        "description": "Generate a structured course outline immediately when the user requests to create, generate, or make a course. Call this function as soon as the user mentions a course topic or subject, even if minimal details are provided. Use the available information to create a comprehensive course.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_request": {
                    "type": "string",
                    "description": "The user's original request for course generation, including any specific requirements or topics they mentioned"
                },
                "title": {
                    "type": "string",
                    "description": "Desired course title (if user specified one)"
                },
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific topics or subjects the user wants in the course (if mentioned)"
                }
            },
            "required": ["user_request"]
        }
    }

