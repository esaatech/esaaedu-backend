"""
GeminiGrader - Simplified AI grading service

Frontend-centric design:
- Frontend sends: question details, student answer, correct answer, context
- Backend returns: points_earned, feedback
- NO database saves - returns only
- Frontend manages state and saving

Usage:
    grader = GeminiGrader()
    
    # Grade single question
    result = grader.grade_question(
        question_text="...",
        question_type="essay",
        student_answer="...",
        points_possible=5,
        correct_answer="...",  # Optional
        explanation="...",  # Optional
        assignment_context={...}  # Optional
    )
    
    # Returns: {"points_earned": 3, "feedback": "...", "confidence": 0.85}

API Endpoint:
    POST /api/teacher/assignments/{assignment_id}/grading/{submission_id}/ai-grade
    
    Request Body:
    {
        "questions": [
            {
                "question_id": "q1",
                "question_text": "...",
                "question_type": "essay",
                "student_answer": "...",
                "points_possible": 5,
                "correct_answer": "...",
                "explanation": "..."
            }
        ],
        "assignment_context": {...}  // Optional
    }
    
    Response:
    {
        "grades": [
            {
                "question_id": "q1",
                "points_earned": 3,
                "points_possible": 5,
                "feedback": "...",
                "confidence": 0.85
            }
        ]
    }
"""
import logging
import json
from typing import Dict, List, Optional, Any
from .gemini_service import GeminiService

logger = logging.getLogger(__name__)


class GeminiGrader:
    """
    Simplified AI grading service.
    
    Frontend-centric: Receives question data, returns grades.
    No database operations - purely computational.
    Frontend handles state management and saving.
    """
    
    def __init__(self):
        """Initialize with GeminiService instance."""
        self.gemini_service = GeminiService()
        logger.info("GeminiGrader initialized")
    
    def grade_question(
        self,
        question_text: str,
        question_type: str,
        student_answer: str,
        points_possible: int,
        correct_answer: Optional[str] = None,
        explanation: Optional[str] = None,
        assignment_context: Optional[Dict[str, Any]] = None,
        rubric: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Grade a single question using AI.
        
        Args:
            question_text: The question text
            question_type: Type of question ('essay', 'fill_blank', 'short_answer', etc.)
            student_answer: Student's answer
            points_possible: Maximum points for this question
            correct_answer: Expected/correct answer (optional, for reference)
            explanation: Question explanation (optional)
            assignment_context: Optional assignment context (passage, lesson info, etc.)
            rubric: Optional rubric for essay questions
            
        Returns:
            Dictionary with:
            - 'points_earned': Points awarded (0 to points_possible)
            - 'feedback': Constructive feedback
            - 'confidence': Confidence score (0.0-1.0)
            - 'error': Error message if grading failed (optional)
            
        Note:
            If question cannot be graded (insufficient info, unclear question, etc.),
            returns points_earned=0 with feedback explaining why.
        """
        try:
            # Build grading prompt
            prompt = self._build_grading_prompt(
                question_text=question_text,
                question_type=question_type,
                student_answer=student_answer,
                correct_answer=correct_answer,
                explanation=explanation,
                points_possible=points_possible,
                rubric=rubric,
                assignment_context=assignment_context
            )
            
            # Get system instruction
            system_instruction = self._get_system_instruction(
                question_type=question_type,
                assignment_context=assignment_context
            )
            
            # Get grading schema
            schema = self._get_grading_schema()
            
            # Generate grade using GeminiService
            response = self.gemini_service.generate(
                system_instruction=system_instruction,
                prompt=prompt,
                response_schema=schema,
                temperature=0.3  # Lower temperature for consistent grading
            )
            
            # Parse and validate response
            grading_result = self._parse_grading_response(
                response=response['parsed'],
                points_possible=points_possible
            )
            
            return grading_result
            
        except Exception as e:
            logger.error(f"Error grading question: {e}", exc_info=True)
            return {
                'points_earned': 0,
                'feedback': f'Error occurred during AI grading: {str(e)}. Please grade manually.',
                'confidence': 0.0,
                'error': str(e)
            }
    
    def grade_questions_batch(
        self,
        questions: List[Dict[str, Any]],
        assignment_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Grade multiple questions in batch.
        
        Args:
            questions: List of question dictionaries with:
                - question_id (required)
                - question_text (required)
                - question_type (required)
                - student_answer (required)
                - points_possible (required)
                - correct_answer (optional)
                - explanation (optional)
                - rubric (optional, for essays)
            assignment_context: Optional assignment context shared across all questions
            
        Returns:
            Dictionary with:
            - 'grades': List of grading results, one per question
            - 'total_score': Sum of points earned
            - 'total_possible': Sum of points possible
        """
        logger.info(f"Batch grading {len(questions)} questions")
        
        grades = []
        total_score = 0
        total_possible = 0
        
        for question_data in questions:
            question_id = question_data.get('question_id')
            if not question_id:
                logger.warning("Question missing question_id, skipping")
                continue
            
            try:
                grade_result = self.grade_question(
                    question_text=question_data.get('question_text', ''),
                    question_type=question_data.get('question_type', ''),
                    student_answer=question_data.get('student_answer', ''),
                    points_possible=question_data.get('points_possible', 0),
                    correct_answer=question_data.get('correct_answer'),
                    explanation=question_data.get('explanation'),
                    rubric=question_data.get('rubric'),
                    assignment_context=assignment_context
                )
                
                # Add question_id to result
                grade_result['question_id'] = question_id
                grades.append(grade_result)
                
                total_score += grade_result.get('points_earned', 0)
                total_possible += question_data.get('points_possible', 0)
                
            except Exception as e:
                logger.error(f"Error grading question {question_id}: {e}", exc_info=True)
                grades.append({
                    'question_id': question_id,
                    'points_earned': 0,
                    'points_possible': question_data.get('points_possible', 0),
                    'feedback': f'Error grading this question: {str(e)}. Please grade manually.',
                    'confidence': 0.0,
                    'error': str(e)
                })
        
        return {
            'grades': grades,
            'total_score': total_score,
            'total_possible': total_possible
        }
    
    def _build_grading_prompt(
        self,
        question_text: str,
        question_type: str,
        student_answer: str,
        points_possible: int,
        correct_answer: Optional[str] = None,
        explanation: Optional[str] = None,
        rubric: Optional[str] = None,
        assignment_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build grading prompt with all context.
        
        Handles edge cases:
        - Missing information → AI should not grade
        - Unclear questions → AI should not grade
        - Insufficient context → AI should not grade
        """
        prompt_parts = []
        
        # Add assignment context if available
        if assignment_context:
            prompt_parts.append("ASSIGNMENT CONTEXT:")
            if assignment_context.get('passage_text'):
                prompt_parts.append(f"Passage: {assignment_context['passage_text']}")
            if assignment_context.get('lesson_content'):
                prompt_parts.append(f"Lesson Content: {assignment_context['lesson_content']}")
            if assignment_context.get('learning_objectives'):
                prompt_parts.append(f"Learning Objectives: {', '.join(assignment_context['learning_objectives'])}")
            prompt_parts.append("")
        
        # Add question
        prompt_parts.append("QUESTION:")
        prompt_parts.append(question_text)
        prompt_parts.append("")
        
        # Add correct answer or model answer if available
        if correct_answer:
            prompt_parts.append("EXPECTED ANSWER (for reference):")
            prompt_parts.append(str(correct_answer))
            prompt_parts.append("")
        
        # Add rubric if essay
        if question_type == 'essay' and rubric:
            prompt_parts.append("RUBRIC:")
            prompt_parts.append(rubric)
            prompt_parts.append("")
        
        # Add explanation if available
        if explanation:
            prompt_parts.append("EXPLANATION:")
            prompt_parts.append(explanation)
            prompt_parts.append("")
        
        # Add student answer
        prompt_parts.append("STUDENT ANSWER:")
        if isinstance(student_answer, dict):
            # Handle fill-in-the-blank answers
            prompt_parts.append(json.dumps(student_answer, indent=2))
        else:
            prompt_parts.append(str(student_answer))
        prompt_parts.append("")
        
        # Add grading instructions
        prompt_parts.append("GRADING INSTRUCTIONS:")
        prompt_parts.append(f"- Points possible: {points_possible}")
        prompt_parts.append("- Grade based on understanding of the concept, not just exact match")
        prompt_parts.append("- Provide constructive feedback written in second person (use 'you' and 'your'), as if you are the teacher directly addressing the student")
        prompt_parts.append("- Write feedback naturally and conversationally - do not use prefixes like 'Reasoning:' or 'Feedback:'")
        prompt_parts.append("- If question is unclear, answer is unclear, or insufficient information provided, award 0 points and explain why grading is not possible")
        if question_type == 'fill_blank':
            prompt_parts.append("- Consider partial credit for close answers that show understanding")
        prompt_parts.append("")
        
        prompt_parts.append("Please grade this answer and provide points_earned and feedback. The feedback should be written directly to the student in second person.")
        
        return "\n".join(prompt_parts)
    
    def _get_system_instruction(
        self,
        question_type: str,
        assignment_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Get system instruction with clear guidelines.
        
        Includes instructions to NOT grade if:
        - Question is unclear
        - Student answer is unclear
        - Insufficient information provided
        """
        base_instruction = """You are an expert educational grader writing feedback directly to students. Your role is to evaluate student answers with:
- Focus on understanding and ideas, not just correctness
- Provide constructive feedback written in second person (use 'you' and 'your') - write as if you are the teacher speaking directly to the student
- Write feedback naturally and conversationally - avoid formal prefixes like "Reasoning:", "Feedback:", or "The answer is..."
- Use phrases like "Your answer..." or "You got..." instead of "The answer is..." or "The student's answer..."
- Award partial credit when appropriate
- Consider context and meaning

IMPORTANT: If you cannot grade the question due to:
- Unclear or ambiguous question
- Unclear or incomplete student answer
- Insufficient information or context
- Question/image not understandable

Then award 0 points and provide feedback explaining why grading is not possible (e.g., "Unable to grade: question is unclear" or "Unable to grade: insufficient information provided").
"""
        
        if question_type == 'essay':
            base_instruction += "\nFor essay questions:\n"
            base_instruction += "- Evaluate the student's understanding of the concept\n"
            base_instruction += "- Check for complete sentences and proper grammar\n"
            base_instruction += "- Award points based on how well they demonstrate understanding\n"
            base_instruction += "- Provide specific feedback on what they did well and what needs improvement\n"
        
        elif question_type == 'fill_blank':
            base_instruction += "\nFor fill-in-the-blank questions:\n"
            base_instruction += "- Award partial credit for close answers that show understanding\n"
            base_instruction += "- Consider variations in wording that convey the same idea\n"
            base_instruction += "- Focus on whether the student understands the concept\n"
        
        return base_instruction
    
    def _get_grading_schema(self) -> Dict[str, Any]:
        """
        Get JSON schema for grading response.
        
        Always returns same schema regardless of question type.
        """
        return {
            "type": "object",
            "properties": {
                "points_earned": {
                    "type": "number",
                    "description": "Points awarded (0 to points_possible, can be decimal for partial credit). Use 0 if question cannot be graded due to unclear question/answer or insufficient information."
                },
                "feedback": {
                    "type": "string",
                    "description": "Constructive feedback written directly to the student in second person (use 'you' and 'your'). Write naturally and conversationally - do not use prefixes like 'Reasoning:' or 'Feedback:'. The feedback should be self-contained and complete. If unable to grade, explain why (e.g., 'Unable to grade: question is unclear')."
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence in the grading (0.0 to 1.0)",
                    "minimum": 0.0,
                    "maximum": 1.0
                }
            },
            "required": ["points_earned", "feedback"]
        }
    
    def _parse_grading_response(
        self,
        response: Dict[str, Any],
        points_possible: int
    ) -> Dict[str, Any]:
        """
        Parse and validate AI grading response.
        
        Ensures points are within valid range.
        Handles missing fields gracefully.
        """
        if not response:
            raise ValueError("Empty response from AI")
        
        # Extract fields
        points_earned = response.get('points_earned', 0)
        feedback = response.get('feedback', '')
        confidence = response.get('confidence', 0.8)
        
        # Validate points
        if points_earned < 0:
            points_earned = 0
        if points_earned > points_possible:
            points_earned = points_possible
        
        # Use feedback directly - it should be self-contained and written in second person
        # Remove any "Reasoning:" prefixes that might have been added by the AI
        cleaned_feedback = feedback.strip()
        if cleaned_feedback.startswith("Reasoning:"):
            cleaned_feedback = cleaned_feedback.replace("Reasoning:", "").strip()
        if cleaned_feedback.startswith("Feedback:"):
            cleaned_feedback = cleaned_feedback.replace("Feedback:", "").strip()
        
        return {
            'points_earned': float(points_earned),
            'feedback': cleaned_feedback,
            'confidence': float(confidence) if confidence else 0.8
        }