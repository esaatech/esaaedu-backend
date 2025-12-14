"""
Course Recommendation Service
Handles filtering and scoring of courses based on assessment data
"""
import re
from typing import List, Dict, Optional, Tuple
from courses.models import Course


# Maps assessment interest areas to course categories
INTEREST_TO_CATEGORY_MAP = {
    'Coding': ['Programming', 'Computer Science', 'Mobile App Development', 'Web Development'],
    'Robotics': ['Robotics', 'Internet of Things (IoT)', 'Engineering'],
    'Electronics': ['Internet of Things (IoT)', 'Robotics', 'Engineering'],
    'Math Skills': ['Mathematics', 'Data Science'],
    'Game Development': ['Game Development'],
    'Web Development': ['Web Development'],
    '3D Design': ['Creative Technology'],
    'AI for Kids': ['Artificial Intelligence'],
    'General STEM Exploration': ['Science', 'Mathematics', 'Physics', 'Chemistry', 'Biology'],
}


def normalize_category(category: Optional[str]) -> str:
    """Normalizes category name for matching (handles variations)"""
    if not category or not isinstance(category, str):
        return ''
    return category.strip()


def parse_age_range(age_range: Optional[str]) -> Optional[Tuple[int, int]]:
    """Parses age range string (e.g., 'Ages 6-10') and returns (min, max)"""
    if not age_range:
        return None
    
    # Match patterns like "Ages 6-10", "6-10", "Ages 8-12", etc.
    # Use search() instead of match() to find the pattern anywhere in the string
    match = re.search(r'(\d+)\s*-\s*(\d+)', age_range)
    if match:
        min_age = int(match.group(1))
        max_age = int(match.group(2))
        return (min_age, max_age)
    
    return None


def is_age_match(student_age: int, course_age_range: Optional[str]) -> bool:
    """Checks if student age falls within course age range (inclusive)"""
    if not course_age_range:
        return False
    
    age_range = parse_age_range(course_age_range)
    if not age_range:
        return False
    
    min_age, max_age = age_range
    return min_age <= student_age <= max_age


def is_category_match(interest_areas: List[str], course_category: Optional[str]) -> bool:
    """Checks if any interest area matches the course category"""
    if not course_category:
        return False
    
    normalized_course_category = normalize_category(course_category)
    if not normalized_course_category:
        return False
    
    for interest in interest_areas:
        categories = INTEREST_TO_CATEGORY_MAP.get(interest, [])
        if any(normalize_category(cat) == normalized_course_category for cat in categories):
            return True
    
    return False


def get_category_priority(interest_areas: List[str], course_category: str) -> int:
    """Gets priority score for category match (higher for specific matches)"""
    priority = 0
    normalized_course_category = normalize_category(course_category)
    
    for interest in interest_areas:
        categories = INTEREST_TO_CATEGORY_MAP.get(interest, [])
        
        if any(normalize_category(cat) == normalized_course_category for cat in categories):
            # General STEM Exploration gets lower priority
            if interest == 'General STEM Exploration':
                priority = max(priority, 1)
            else:
                priority = max(priority, 2)
    
    return priority


def get_skills_alignment_score(
    computer_skills_level: Optional[str],
    course_level: str
) -> int:
    """
    Gets computer skills alignment score
    Beginner skills → prioritize beginner courses
    Advanced skills → prioritize advanced/intermediate courses
    """
    if not computer_skills_level:
        return 0
    
    # Beginner students → beginner courses get highest score
    if computer_skills_level == 'beginner':
        if course_level == 'beginner':
            return 3
        if course_level == 'intermediate':
            return 1
        return 0
    
    # Intermediate students → intermediate and beginner courses
    if computer_skills_level == 'intermediate':
        if course_level == 'intermediate':
            return 3
        if course_level == 'beginner':
            return 2
        if course_level == 'advanced':
            return 1
    
    # Advanced students → advanced and intermediate courses
    if computer_skills_level == 'advanced':
        if course_level == 'advanced':
            return 3
        if course_level == 'intermediate':
            return 2
        if course_level == 'beginner':
            return 1
    
    return 0


def recommend_courses(
    student_age: int,
    interest_areas: List[str],
    computer_skills_level: Optional[str],
    limit: int = 5
) -> List[Dict]:
    """
    Recommends courses based on assessment data
    
    Args:
        student_age: Student's age (3-18)
        interest_areas: List of interest areas selected
        computer_skills_level: Student's computer skills level ('beginner', 'intermediate', 'advanced')
        limit: Maximum number of recommendations to return (default: 5)
    
    Returns:
        List of recommended courses with matchScore and matchReasons
    """
    # Get all published courses (no pagination limit for filtering)
    courses = Course.objects.filter(status='published').select_related('teacher')
    
    scored_courses = []
    
    for course in courses:
        match_reasons = []
        score = 0
        
        # Age match (50 points if match, 0 if no match)
        age_match = is_age_match(student_age, course.age_range)
        if age_match:
            score += 50
            match_reasons.append(f"Perfect for ages {course.age_range}")
        
        # Category match (40 points if match, 0 if no match)
        category_match = is_category_match(interest_areas, course.category)
        if category_match:
            score += 40
            category_priority = get_category_priority(interest_areas, course.category)
            if category_priority == 2:
                # Find which interest matched
                matched_interest = None
                for interest in interest_areas:
                    categories = INTEREST_TO_CATEGORY_MAP.get(interest, [])
                    if any(normalize_category(cat) == normalize_category(course.category) for cat in categories):
                        matched_interest = interest
                        break
                match_reasons.append(f"Matches your interest in {matched_interest or 'STEM'}")
            else:
                match_reasons.append("Great for STEM exploration")
        
        # REQUIRED: Category match is mandatory
        if not category_match:
            continue  # Skip courses that don't match selected interests
        
        # REQUIRED: Age match is also mandatory
        if not age_match:
            continue  # Skip courses outside student's age range
        
        # Computer skills requirement matching
        required_skills = course.required_computer_skills_level
        
        if computer_skills_level and required_skills and required_skills != 'any':
            # Course has specific requirement - check if student meets it
            
            # Perfect match: student skills exactly match requirement
            if required_skills == computer_skills_level:
                score += 20  # High bonus for perfect match
                match_reasons.append("Perfect skill level match")
            # Student has higher skills than required - still acceptable
            elif (
                (required_skills == 'beginner' and computer_skills_level in ['intermediate', 'advanced']) or
                (required_skills == 'intermediate' and computer_skills_level == 'advanced')
            ):
                score += 10  # Bonus for exceeding requirements
                match_reasons.append("Your skills exceed requirements")
            # Student doesn't meet minimum requirement - EXCLUDE this course
            else:
                continue  # Skip courses where student doesn't meet minimum requirement
        
        elif computer_skills_level and required_skills == 'any':
            # Course accepts any skill level - give small bonus
            score += 5
        
        elif computer_skills_level and (not required_skills or required_skills == 'any'):
            # Fallback: if course doesn't have required_computer_skills_level set, use course.level
            skills_score = get_skills_alignment_score(computer_skills_level, course.level)
            if skills_score > 0:
                score += skills_score * 3  # Up to 9 points
                if skills_score == 3:
                    match_reasons.append("Perfect skill level match")
        
        # Featured/Popular bonus
        if course.featured:
            score += 5
        if course.popular:
            score += 3
        
        # Add course to scored list
        scored_courses.append({
            'course': course,
            'matchScore': score,
            'matchReasons': match_reasons,
        })
    
    # Sort by score (highest first), then by enrollment count
    scored_courses.sort(
        key=lambda x: (-x['matchScore'], -(x['course'].enrolled_students_count or 0))
    )
    
    # Return top N courses
    return scored_courses[:limit]

