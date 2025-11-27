"""
GeminiAssessmentService - Service for generating assessment questions (tests/exams) using Gemini AI

This service extends GeminiService to provide assessment question generation functionality.
It supports multiple lessons and all question types (multiple choice, true/false, fill blank, short answer, essay).

Usage:
    from ai.gemini_assessment_service import GeminiAssessmentService
    
    service = GeminiAssessmentService()
    
    result = service.generate(
        system_instruction="You are an expert test creator...",
        lesson_contents=[{"lesson_title": "...", "content": "..."}, ...],
        assessment_type="test",
        temperature=0.7,
        total_questions=10,
        multiple_choice_count=5,
        true_false_count=3,
        fill_blank_count=2
    )
"""
import logging
import sys
import os
from typing import Dict, Any, Optional, List, Union
from vertexai.generative_models import Part

# Handle both module import and direct execution
try:
    from .gemini_service import GeminiService
    from .schemas import get_assessment_generation_schema
except ImportError:
    # If running as script, add parent directory to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ai.gemini_service import GeminiService
    from ai.schemas import get_assessment_generation_schema

logger = logging.getLogger(__name__)


class GeminiAssessmentService:
    """
    Service for generating assessment questions (tests/exams) using Gemini AI.
    
    Extends GeminiService to provide assessment-specific functionality.
    Supports multiple lessons and all question types.
    """
    
    def __init__(self):
        """Initialize the service with base GeminiService"""
        self.gemini_service = GeminiService()
        logger.info("GeminiAssessmentService initialized")
    
    def generate(
        self,
        system_instruction: str,
        lesson_contents: List[Dict[str, Any]],
        assessment_type: str = "test",
        content: Union[str, List[Part], None] = None,
        file_parts: Optional[List[Part]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        model_name: Optional[str] = None,
        total_questions: int = 10,
        multiple_choice_count: int = 0,
        true_false_count: int = 0,
        fill_blank_count: int = 0,
        short_answer_count: int = 0,
        essay_count: int = 0
    ) -> Dict[str, Any]:
        """
        Generate assessment questions using Gemini AI.
        
        Args:
            system_instruction: System instruction/prompt from frontend
            lesson_contents: List of dicts with lesson info and content
                [{"lesson_title": "...", "lesson_order": 1, "content": "..."}, ...]
            assessment_type: "test" or "exam"
            content: Combined text content from all selected materials OR None if using file_parts
            file_parts: Optional list of Part objects (for direct file uploads like PDFs, Word docs)
            temperature: Temperature for generation (0.0-1.0, default: 0.7)
            max_tokens: Maximum tokens in response (optional)
            model_name: Optional model name to use (overrides default from config)
            total_questions: Total number of questions to generate
            multiple_choice_count: Number of multiple choice questions
            true_false_count: Number of true/false questions
            fill_blank_count: Number of fill-in-the-blank questions
            short_answer_count: Number of short answer questions
            essay_count: Number of essay questions
            
        Returns:
            Dictionary containing generated questions:
            {
                'questions': List[Dict]  # Each question has question_text, type, points, content, explanation
            }
            
        Raises:
            ValueError: If required parameters are missing
            Exception: If API call fails
        """
        if not system_instruction:
            raise ValueError("system_instruction is required")
        if not lesson_contents and not content and not file_parts:
            raise ValueError("Either lesson_contents, content (text), or file_parts must be provided")
        
        try:
            # Validate question counts
            total_specified = (
                multiple_choice_count + true_false_count + fill_blank_count + 
                short_answer_count + essay_count
            )
            
            if total_specified != total_questions:
                # Auto-adjust to match total
                if total_specified > total_questions:
                    # Reduce proportionally
                    ratio = total_questions / total_specified if total_specified > 0 else 1
                    multiple_choice_count = int(multiple_choice_count * ratio)
                    true_false_count = int(true_false_count * ratio)
                    fill_blank_count = int(fill_blank_count * ratio)
                    short_answer_count = int(short_answer_count * ratio)
                    essay_count = total_questions - (multiple_choice_count + true_false_count + fill_blank_count + short_answer_count)
                else:
                    # Increase to match total - distribute evenly among non-zero types
                    non_zero_types = []
                    if multiple_choice_count > 0:
                        non_zero_types.append('mc')
                    if true_false_count > 0:
                        non_zero_types.append('tf')
                    if fill_blank_count > 0:
                        non_zero_types.append('fb')
                    if short_answer_count > 0:
                        non_zero_types.append('sa')
                    if essay_count > 0:
                        non_zero_types.append('essay')
                    
                    if non_zero_types:
                        remainder = total_questions - total_specified
                        per_type = remainder // len(non_zero_types)
                        extra = remainder % len(non_zero_types)
                        
                        if 'mc' in non_zero_types:
                            multiple_choice_count += per_type + (1 if extra > 0 else 0)
                            extra = max(0, extra - 1)
                        if 'tf' in non_zero_types:
                            true_false_count += per_type + (1 if extra > 0 else 0)
                            extra = max(0, extra - 1)
                        if 'fb' in non_zero_types:
                            fill_blank_count += per_type + (1 if extra > 0 else 0)
                            extra = max(0, extra - 1)
                        if 'sa' in non_zero_types:
                            short_answer_count += per_type + (1 if extra > 0 else 0)
                            extra = max(0, extra - 1)
                        if 'essay' in non_zero_types:
                            essay_count += per_type + (1 if extra > 0 else 0)
            
            # Build content section
            content_section = ""
            if lesson_contents:
                # Build content from lesson_contents
                lesson_sections = []
                for lesson_info in lesson_contents:
                    lesson_title = lesson_info.get('lesson_title', 'Untitled Lesson')
                    lesson_order = lesson_info.get('lesson_order', 0)
                    lesson_content = lesson_info.get('content', '')
                    material_title = lesson_info.get('material_title', '')
                    material_type = lesson_info.get('material_type', '')
                    
                    section = f"=== Lesson {lesson_order}: {lesson_title} ===\n"
                    if material_title:
                        section += f"Material: {material_title} ({material_type})\n"
                    section += f"Content:\n{lesson_content}\n"
                    lesson_sections.append(section)
                
                content_section = "\n\n".join(lesson_sections)
            elif isinstance(content, str) and content.strip():
                content_section = f"Content:\n{content}\n\n"
            elif file_parts:
                content_section = "Content: See attached document(s).\n\n"
            
            # Build question type requirements
            question_type_requirements = []
            if multiple_choice_count > 0:
                question_type_requirements.append(f"Exactly {multiple_choice_count} multiple choice question(s)")
            if true_false_count > 0:
                question_type_requirements.append(f"Exactly {true_false_count} true/false question(s)")
            if fill_blank_count > 0:
                question_type_requirements.append(f"Exactly {fill_blank_count} fill-in-the-blank question(s)")
            if short_answer_count > 0:
                question_type_requirements.append(f"Exactly {short_answer_count} short answer question(s)")
            if essay_count > 0:
                question_type_requirements.append(f"Exactly {essay_count} essay question(s)")
            
            question_types_str = "\n".join([f"- {req}" for req in question_type_requirements])
            
            # Build prompt
            prompt = f"""Generate a comprehensive {assessment_type} with questions based on the following course materials.

{content_section}

Generate exactly {total_questions} {assessment_type} questions:
{question_types_str}

CRITICAL REQUIREMENTS:
1. Topic Coverage: Generate at least one question from every lesson/topic provided.
   - If the number of lessons is less than the total questions requested, prioritize the most recent lessons first.
   - Ensure comprehensive coverage: each lesson should contribute at least one question before any lesson receives multiple questions.
   - When distributing additional questions beyond one per lesson, prioritize lessons in reverse chronological order (most recent first).

2. Question Quality:
   - Create clear, unambiguous questions that test genuine understanding
   - Ensure questions are appropriate for the educational level
   - Provide accurate and well-structured correct answers
   - Include explanations that help students understand the reasoning

3. Question Type Distribution:
   - Follow the specified counts for each question type exactly
   - Distribute question types evenly across lessons when possible
   - Ensure variety within each lesson's questions

4. Content Alignment:
   - Base all questions directly on the provided lesson materials
   - Ensure questions test concepts actually covered in the materials
   - Avoid questions that require knowledge not present in the materials

5. For Multiple Choice Questions:
   - CRITICAL: Must include "options" array with at least 2 options (preferably 4)
   - CRITICAL: Must include "correct_answer" field specifying which option is correct (use the exact option text)
   - Ensure only one correct answer
   - Make distractors plausible but clearly incorrect
   - OPTIONAL but RECOMMENDED: Include "full_options" object with explanations:
     * For each option, provide an explanation of why it's correct or incorrect
     * Structure: {{"full_options": {{"options": [{{"id": "option-0", "text": "option text", "isCorrect": true/false, "explanation": "why correct/wrong"}}]}}}}
     * The "id" should be "option-0", "option-1", etc. based on position
     * The "isCorrect" should match whether this option is the correct_answer
     * The "explanation" should explain why the option is correct or why it's wrong

6. For True/False Questions:
   - CRITICAL: Must include "correct_answer" field with "true" or "false"
   - Ensure clear true/false answers
   - Test important concepts, not trivial facts
   - OPTIONAL but RECOMMENDED: Include "full_options" object with explanations:
     * Structure: {{"full_options": {{"trueOption": {{"id": "true", "text": "True", "isCorrect": true/false, "explanation": "..."}}, "falseOption": {{"id": "false", "text": "False", "isCorrect": true/false, "explanation": "..."}}}}}}
     * Provide explanations for both true and false options

7. For Fill-in-the-Blank Questions:
   - Provide clear blanks and correct answers
   - Test key concepts from the material

8. For Short Answer Questions:
   - Provide expected answer
   - May accept variations if appropriate

9. For Essay Questions:
   - Provide detailed model answer in explanation field
   - Include instructions for students in content.instructions if needed
   - Model answer should demonstrate expected depth and quality

GENERATION STRATEGY:
- First pass: Generate one question from each lesson (prioritizing most recent lessons if total lessons < total questions)
- Second pass: Distribute remaining questions across lessons, prioritizing most recent lessons first
- Ensure balanced representation: no lesson should be significantly over-represented unless it's the most recent content

Remember: {assessment_type.capitalize()}s should comprehensively assess student knowledge across all covered topics while emphasizing recent material when question count exceeds lesson count."""
            
            # Get schema for structured output
            response_schema = get_assessment_generation_schema()
            
            # Call base service with text and/or file parts
            response = self.gemini_service.generate(
                system_instruction=system_instruction,
                prompt=prompt,
                response_schema=response_schema,
                temperature=temperature,
                max_tokens=max_tokens,
                file_parts=file_parts,
                model_name=model_name
            )
            
            # Extract parsed data
            if not response.get('parsed'):
                raise ValueError("Failed to parse AI response")
            
            parsed_data = response['parsed']
            
            # Validate and structure result
            result = {
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
                    # Ensure options array exists and has at least 2 items
                    if 'options' not in validated_q['content'] or not isinstance(validated_q['content']['options'], list):
                        validated_q['content']['options'] = []
                    elif len(validated_q['content']['options']) < 2:
                        logger.warning(f"Multiple choice question has less than 2 options, adding defaults")
                        while len(validated_q['content']['options']) < 2:
                            validated_q['content']['options'].append('')
                    
                    # Ensure correct_answer exists
                    if 'correct_answer' not in validated_q['content'] or not validated_q['content']['correct_answer']:
                        # Try to infer from full_options if available
                        if validated_q['content'].get('full_options', {}).get('options'):
                            correct_option = next(
                                (opt for opt in validated_q['content']['full_options']['options'] if opt.get('isCorrect')),
                                None
                            )
                            if correct_option:
                                validated_q['content']['correct_answer'] = correct_option.get('text', '')
                            else:
                                validated_q['content']['correct_answer'] = validated_q['content']['options'][0] if validated_q['content']['options'] else ''
                        else:
                            validated_q['content']['correct_answer'] = validated_q['content']['options'][0] if validated_q['content']['options'] else ''
                    
                    # Generate full_options if not provided but options exist
                    if 'full_options' not in validated_q['content'] or not validated_q['content'].get('full_options', {}).get('options'):
                        if validated_q['content']['options']:
                            correct_answer_text = validated_q['content']['correct_answer']
                            validated_q['content']['full_options'] = {
                                'options': [
                                    {
                                        'id': f'option-{i}',
                                        'text': option,
                                        'isCorrect': option == correct_answer_text,
                                        'explanation': f"This is {'correct' if option == correct_answer_text else 'incorrect'}."
                                    }
                                    for i, option in enumerate(validated_q['content']['options'])
                                ]
                            }
                            logger.info(f"Generated full_options for multiple choice question with {len(validated_q['content']['options'])} options")
                
                elif validated_q['type'] == 'true_false':
                    # Ensure correct_answer exists
                    if 'correct_answer' not in validated_q['content'] or not validated_q['content']['correct_answer']:
                        # Try to infer from full_options if available
                        if validated_q['content'].get('full_options', {}).get('trueOption', {}).get('isCorrect'):
                            validated_q['content']['correct_answer'] = 'true'
                        elif validated_q['content'].get('full_options', {}).get('falseOption', {}).get('isCorrect'):
                            validated_q['content']['correct_answer'] = 'false'
                        else:
                            validated_q['content']['correct_answer'] = 'true'
                    
                    # Normalize correct_answer to string
                    correct_answer = str(validated_q['content']['correct_answer']).lower()
                    if correct_answer not in ['true', 'false']:
                        correct_answer = 'true'
                    validated_q['content']['correct_answer'] = correct_answer
                    
                    # Generate full_options if not provided
                    if 'full_options' not in validated_q['content'] or not validated_q['content'].get('full_options', {}).get('trueOption'):
                        is_true_correct = validated_q['content']['correct_answer'] == 'true'
                        validated_q['content']['full_options'] = {
                            'trueOption': {
                                'id': 'true',
                                'text': 'True',
                                'isCorrect': is_true_correct,
                                'explanation': 'This is correct.' if is_true_correct else 'This is incorrect.'
                            },
                            'falseOption': {
                                'id': 'false',
                                'text': 'False',
                                'isCorrect': not is_true_correct,
                                'explanation': 'This is correct.' if not is_true_correct else 'This is incorrect.'
                            }
                        }
                        logger.info(f"Generated full_options for true/false question")
                
                elif validated_q['type'] == 'fill_blank':
                    if 'blanks' not in validated_q['content']:
                        validated_q['content']['blanks'] = []
                    if 'correct_answers' not in validated_q['content']:
                        validated_q['content']['correct_answers'] = {}
                
                elif validated_q['type'] == 'short_answer':
                    if 'correct_answer' not in validated_q['content']:
                        validated_q['content']['correct_answer'] = ''
                    if 'accept_variations' not in validated_q['content']:
                        validated_q['content']['accept_variations'] = True
                
                elif validated_q['type'] == 'essay':
                    if 'instructions' not in validated_q['content']:
                        validated_q['content']['instructions'] = ''
                    if 'correct_answer' not in validated_q['content']:
                        validated_q['content']['correct_answer'] = validated_q.get('explanation', '')
                
                validated_questions.append(validated_q)
            
            result['questions'] = validated_questions
            
            logger.info(f"Successfully generated {assessment_type} with {len(result['questions'])} questions")
            return result
            
        except Exception as e:
            logger.error(f"Error generating {assessment_type} questions: {e}", exc_info=True)
            raise

