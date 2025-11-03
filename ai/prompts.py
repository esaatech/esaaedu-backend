"""
System prompts and output schemas for different content generation types
Loads from database (AIPrompt model) - no hardcoded fallbacks
"""
from typing import Dict, Any, Optional, List
import logging
from django.core.cache import cache
from .models import AIPrompt

logger = logging.getLogger(__name__)

# Cache timeout for prompts (5 minutes)
PROMPT_CACHE_TIMEOUT = 300

# Cache timeout for categories (1 hour - they don't change often)
CATEGORY_CACHE_TIMEOUT = 3600

def get_course_categories() -> List[str]:
    """
    Fetch available course categories from CourseCategory model.
    Uses caching to avoid repeated database queries.
    
    Returns:
        List of category names
    """
    cache_key = 'ai_course_categories'
    categories = cache.get(cache_key)
    
    if categories is None:
        try:
            from courses.models import CourseCategory
            categories = list(CourseCategory.objects.values_list('name', flat=True).order_by('name'))
            # Always include "Others" as a fallback option
            if 'Others' not in categories:
                categories.append('Others')
            cache.set(cache_key, categories, CATEGORY_CACHE_TIMEOUT)
            logger.debug(f"Fetched {len(categories)} categories from database")
        except Exception as e:
            logger.error(f"Error fetching categories from database: {e}")
            # If CourseCategory doesn't exist yet, return just "Others"
            categories = ['Others']
            cache.set(cache_key, categories, CATEGORY_CACHE_TIMEOUT)
    
    return categories


def format_categories_list() -> str:
    """
    Format categories list as a bulleted list for prompts.
    
    Returns:
        Formatted string with categories
    """
    categories = get_course_categories()
    return "\n".join(f"- {cat}" for cat in categories)


def invalidate_category_cache():
    """
    Invalidate the category cache.
    Call this when categories are added/updated/deleted.
    """
    cache.delete('ai_course_categories')
    logger.debug("Category cache invalidated")


def invalidate_prompt_cache(prompt_type: str = None):
    """
    Invalidate prompt cache.
    
    Args:
        prompt_type: Specific prompt type to invalidate, or None to invalidate all
    """
    if prompt_type:
        cache.delete(f'ai_prompt_{prompt_type}')
        logger.debug(f"Prompt cache invalidated for: {prompt_type}")
    else:
        # Invalidate all prompts (would need to know all types - for now just log)
        logger.debug("All prompt caches should be invalidated")


def get_prompt(prompt_type: str, use_cache: bool = True) -> Optional[AIPrompt]:
    """
    Get active prompt from database with optional caching.
    
    Args:
        prompt_type: Type of prompt (e.g., 'course_generation')
        use_cache: Whether to use cache (default: True)
    
    Returns:
        AIPrompt instance or None if not found
    
    Raises:
        ValueError: If prompt not found (no fallback - must exist in DB)
    """
    cache_key = f'ai_prompt_{prompt_type}'
    
    if use_cache:
        prompt = cache.get(cache_key)
        if prompt:
            logger.debug(f"Loaded prompt from cache: {prompt_type}")
            return prompt
    
    try:
        prompt = AIPrompt.objects.filter(
            prompt_type=prompt_type,
            is_active=True
        ).first()
        
        if prompt:
            if use_cache:
                cache.set(cache_key, prompt, PROMPT_CACHE_TIMEOUT)
            logger.debug(f"Loaded prompt from database: {prompt_type}")
            return prompt
        else:
            error_msg = f"No active prompt found in database for type: {prompt_type}. Please create one in Django Admin."
            logger.error(error_msg)
            raise ValueError(error_msg)
    except Exception as e:
        error_msg = f"Error loading prompt from database: {e}"
        logger.error(error_msg)
        raise ValueError(error_msg)


def get_course_generation_prompt(
    user_request: str,
    context: Dict[str, Any] = None
) -> str:
    """
    Generate prompt for course creation based on user request.
    Loads prompt from database (required - no fallback).
    
    Args:
        user_request: User's natural language request (e.g., "Create a course on Scratch programming")
        context: Optional context like age_range, existing_category, etc.
    
    Returns:
        Formatted prompt string for Gemini
    
    Raises:
        ValueError: If prompt not found in database
    """
    # Get prompt from database
    prompt_obj = get_prompt('course_generation')
    
    # Add categories to context (will be injected by format_prompt)
    if context is None:
        context = {}
    
    # format_prompt will automatically inject categories
    return prompt_obj.format_prompt(user_request, context)


def get_course_generation_schema() -> Dict[str, Any]:
    """
    Get output schema for course generation from database.
    Dynamically updates category enum with current categories.
    
    Returns:
        JSON schema dictionary
    
    Raises:
        ValueError: If prompt not found in database
    """
    prompt_obj = get_prompt('course_generation')
    
    if not prompt_obj or not prompt_obj.output_schema:
        raise ValueError("Course generation prompt not found in database or missing schema")
    
    # Get current categories and update schema
    schema = prompt_obj.output_schema.copy()
    categories = get_course_categories()
    
    # Update category field in schema to include current categories
    if 'properties' in schema and 'category' in schema['properties']:
        schema['properties']['category'] = {
            "type": "string",
            "description": f"Course category. Must be one of: {', '.join(categories)}. If no category matches, use 'Others'.",
        }
        # Note: We don't use enum here because categories can change - we validate in the consumer
    
    return schema


def get_course_generation_system_instruction() -> str:
    """
    Get system instruction for Gemini when generating course content.
    Loads from database and formats with current categories.
    
    Returns:
        System instruction string
    
    Raises:
        ValueError: If prompt not found in database
    """
    prompt_obj = get_prompt('course_generation')
    
    if not prompt_obj or not prompt_obj.system_instruction:
        raise ValueError("Course generation prompt not found in database or missing system instruction")
    
    # Format categories if placeholder exists
    if '{available_categories}' in prompt_obj.system_instruction:
        categories_list = format_categories_list()
        return prompt_obj.system_instruction.format(available_categories=categories_list)
    
    return prompt_obj.system_instruction


def get_prompt_for_type(
    prompt_type: str,
    user_request: str,
    context: Dict[str, Any] = None
) -> tuple:
    """
    Get complete prompt configuration (prompt, system_instruction, schema) for a given type.
    All from database - no fallbacks.
    
    Args:
        prompt_type: Type of prompt (e.g., 'course_generation')
        user_request: User's request
        context: Optional context
    
    Returns:
        Tuple of (formatted_prompt, system_instruction, schema)
    
    Raises:
        ValueError: If prompt not found in database
    """
    if prompt_type == 'course_generation':
        return (
            get_course_generation_prompt(user_request, context),
            get_course_generation_system_instruction(),
            get_course_generation_schema()
        )
    else:
        # Generic handler for other prompt types
        prompt_obj = get_prompt(prompt_type)
        
        if not prompt_obj:
            raise ValueError(f"No active prompt found in database for type: {prompt_type}. Please create one in Django Admin.")
        
        system_instruction = prompt_obj.system_instruction
        # Format categories if placeholder exists
        if '{available_categories}' in system_instruction:
            categories_list = format_categories_list()
            system_instruction = system_instruction.format(available_categories=categories_list)
        
        return (
            prompt_obj.format_prompt(user_request, context),
            system_instruction,
            prompt_obj.output_schema
        )
