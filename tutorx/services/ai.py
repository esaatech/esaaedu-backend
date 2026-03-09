"""
TutorXAIService - AI service for TutorX block actions

This service extends GeminiService to provide AI-powered actions on content blocks.
Supports actions like "explain more", "give examples", "simplify", etc.

Uses TutorXBlockActionConfig for system instructions (admin-managed, loaded from database).
User prompts are passed as parameters - the service does not handle saving/loading user prompts.

Flow:
1. Frontend loads user instruction when page mounts (from UserTutorXInstruction API)
2. User can edit instruction in frontend UI
3. Frontend sends user_prompt as parameter when calling AI service
4. Backend view handles saving user instruction if user_prompt_changed is True
5. Service combines system instruction (from DB) + user_prompt (from request) + block content

Usage:
    from tutorx.services.ai import TutorXAIService
    
    service = TutorXAIService()
    
    # Explain a block in more detail
    result = service.explain_more(
        block_content="Python is a programming language",
        block_type="text",
        context={"lesson_title": "Introduction to Python"},
        user_prompt="Please explain {block_content} using simple language..."  # Passed from view
    )
    
    # Get examples for a block (without user prompt, uses default)
    result = service.give_examples(
        block_content="Variables store data",
        block_type="text"
    )
"""
import logging
from typing import Dict, Any, Optional, List
from ai.gemini_service import GeminiService

logger = logging.getLogger(__name__)


class TutorXAIService:
    """
    AI service for TutorX block actions.
    
    Extends GeminiService to provide block-specific AI functionality:
    - Explain more: Expand on block content with more detail
    - Give examples: Generate examples related to block content
    - Simplify: Make content easier to understand
    - Summarize: Create a concise summary
    - Generate questions: Create questions based on block content
    
    Designed to work with block-based content in TutorX lessons.
    """
    
    def __init__(self):
        """Initialize the service with base GeminiService"""
        self.gemini_service = GeminiService()
        logger.info("TutorXAIService initialized")
    
    
    def _get_system_instruction(self, action_type: str) -> str:
        """
        Get system instruction from TutorXBlockActionConfig.
        
        Args:
            action_type: Type of action (e.g., 'explain_more', 'give_examples')
            
        Returns:
            System instruction string
            
        Raises:
            ValueError: If no active configuration found
        """
        try:
            from tutorx.models import TutorXBlockActionConfig
            
            config = TutorXBlockActionConfig.objects.filter(
                action_type=action_type,
                is_active=True
            ).first()
            
            if config:
                logger.debug(f"Loaded system instruction for {action_type} from database")
                return config.system_instruction
            else:
                logger.warning(f"No active TutorXBlockActionConfig found for {action_type}, using fallback")
                # Fallback to basic instruction
                return "You are an expert educational assistant helping students learn."
        except Exception as e:
            logger.error(f"Error loading system instruction for {action_type}: {e}", exc_info=True)
            # Fallback
            return "You are an expert educational assistant helping students learn."
    
    def _get_default_user_prompt(self, action_type: str) -> str:
        """
        Get default user prompt from TutorXUserInstructionsDefaults.
        
        Args:
            action_type: Type of action (e.g., 'explain_more', 'give_examples')
            
        Returns:
            Default user prompt string
        """
        try:
            from tutorx.models import TutorXUserInstructionsDefaults
            
            default_config = TutorXUserInstructionsDefaults.objects.filter(
                action_type=action_type,
                is_active=True
            ).first()
            
            if default_config and default_config.default_user_instruction:
                logger.debug(f"Loaded default user instruction for {action_type} from database")
                return default_config.default_user_instruction
            else:
                logger.warning(f"No default user instruction found for {action_type}, using fallback")
                # Fallback to basic prompt
                return f"Please process the following {action_type.replace('_', ' ')} request for: {{block_content}}"
        except Exception as e:
            logger.error(f"Error loading default user instruction for {action_type}: {e}", exc_info=True)
            # Fallback
            return f"Please process the following {action_type.replace('_', ' ')} request for: {{block_content}}"
    
    
    def _build_prompt(
        self,
        action_type: str,
        block_content: str,
        block_type: str = "text",
        context: Optional[Dict[str, Any]] = None,
        user_prompt_text: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Build the final prompt by combining system instruction, user prompt, and block content.
        
        Args:
            action_type: Type of action
            block_content: Content of the block
            block_type: Type of block
            context: Optional context dictionary
            user_prompt_text: Optional user's custom prompt text
            **kwargs: Additional parameters for prompt building
            
        Returns:
            Formatted prompt string
        """
        # Build context section
        context_section = ""
        if context:
            parts = []
            for key, value in context.items():
                if value:
                    parts.append(f"{key}: {value}")
            if parts:
                context_section = "\n\nAdditional context:\n" + "\n".join(f"- {part}" for part in parts)
        
        # If user has a custom prompt, use it
        if user_prompt_text:
            try:
                # Try to format user prompt with block_content and context
                prompt = user_prompt_text.format(
                    block_content=block_content,
                    block_type=block_type,
                    context=context_section if context else "",
                    **{k: v for k, v in (context or {}).items() if v}
                )
                return prompt
            except KeyError:
                # If formatting fails, append block content
                return f"{user_prompt_text}\n\nBlock Content:\n{block_content}{context_section}"
        
        # Default prompt structure if no user prompt
        # This will be customized per action type
        return f"Block Content ({block_type}):\n{block_content}{context_section}"
    
    def explain_more(
        self,
        block_content: str,
        block_type: str = "text",
        context: Optional[Dict[str, Any]] = None,
        user_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate an expanded explanation for a content block.
        
        Args:
            block_content: The content of the block to explain
            block_type: Type of block (text, code, image, diagram)
            context: Optional context dictionary (e.g., {"lesson_title": "...", "target_audience": "..."})
            user_prompt: User prompt (sent from frontend, or None to use default)
            temperature: Temperature for generation (0.0-1.0, default: 0.7)
            max_tokens: Maximum tokens in response (optional)
            
        Returns:
            Dictionary with:
            - 'explanation': Expanded explanation text
            - 'model': Model name used
        """
        if not block_content or not block_content.strip():
            raise ValueError("block_content is required")
        
        # Get system instruction from database (admin-managed)
        system_instruction = self._get_system_instruction('explain_more')
        
        # Use default prompt if not provided
        if not user_prompt:
            user_prompt = self._get_default_user_prompt('explain_more')
        
        # Build prompt using user_prompt (always provided or default)
        prompt = self._build_prompt(
            action_type='explain_more',
            block_content=block_content,
            block_type=block_type,
            context=context,
            user_prompt_text=user_prompt
        )
        
        try:
            response = self.gemini_service.generate(
                system_instruction=system_instruction,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return {
                'explanation': response['raw'],
                'model': response['model']
            }
        except Exception as e:
            logger.error(f"Error in explain_more: {e}", exc_info=True)
            raise
    
    def give_examples(
        self,
        block_content: str,
        block_type: str = "text",
        context: Optional[Dict[str, Any]] = None,
        user_prompt: Optional[str] = None,
        num_examples: int = 3,
        example_type: str = "practical",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate examples related to block content.
        
        Args:
            block_content: The content of the block
            block_type: Type of block (text, code, image, diagram)
            context: Optional context dictionary
            user_prompt: User prompt (sent from frontend, or None to use default)
            num_examples: Number of examples to generate (default: 3)
            example_type: Type of examples ("practical", "real-world", "simple", "advanced")
            temperature: Temperature for generation (0.0-1.0, default: 0.7)
            max_tokens: Maximum tokens in response (optional)
            
        Returns:
            Dictionary with:
            - 'examples': List of example strings
            - 'model': Model name used
        """
        if not block_content or not block_content.strip():
            raise ValueError("block_content is required")
        
        if num_examples < 1 or num_examples > 10:
            raise ValueError("num_examples must be between 1 and 10")
        
        # Get system instruction from database (admin-managed)
        system_instruction = self._get_system_instruction('give_examples')
        
        # Use default prompt if not provided
        if not user_prompt:
            user_prompt = self._get_default_user_prompt('give_examples')
        
        # Build context with example-specific parameters
        example_context = context or {}
        example_context['num_examples'] = num_examples
        example_context['example_type'] = example_type
        
        # Build prompt using user_prompt (always provided or default)
        prompt = self._build_prompt(
            action_type='give_examples',
            block_content=block_content,
            block_type=block_type,
            context=example_context,
            user_prompt_text=user_prompt
        )
        
        try:
            response = self.gemini_service.generate(
                system_instruction=system_instruction,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Parse examples from response (split by newlines, clean up numbering)
            examples_text = response['raw'].strip()
            examples = []
            for line in examples_text.split('\n'):
                line = line.strip()
                if line:
                    # Remove common numbering patterns (1., 1), -, etc.)
                    line = line.lstrip('0123456789.-) ')
                    if line:
                        examples.append(line)
            
            # Limit to requested number
            examples = examples[:num_examples]
            
            return {
                'examples': examples,
                'raw_response': response['raw'],
                'model': response['model']
            }
        except Exception as e:
            logger.error(f"Error in give_examples: {e}", exc_info=True)
            raise
    
    def simplify(
        self,
        block_content: str,
        block_type: str = "text",
        context: Optional[Dict[str, Any]] = None,
        user_prompt: Optional[str] = None,
        target_level: str = "beginner",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Simplify block content to make it easier to understand.
        
        Args:
            block_content: The content of the block to simplify
            block_type: Type of block (text, code, image, diagram)
            context: Optional context dictionary
            user_prompt: User prompt (sent from frontend, or None to use default)
            target_level: Target understanding level ("beginner", "intermediate", "advanced")
            temperature: Temperature for generation (0.0-1.0, default: 0.7)
            max_tokens: Maximum tokens in response (optional)
            
        Returns:
            Dictionary with:
            - 'simplified_content': Simplified version of the content
            - 'model': Model name used
        """
        if not block_content or not block_content.strip():
            raise ValueError("block_content is required")
        
        # Get system instruction from database (admin-managed)
        system_instruction = self._get_system_instruction('simplify')
        
        # Use default prompt if not provided
        if not user_prompt:
            user_prompt = self._get_default_user_prompt('simplify')
        
        # Build context with target_level
        simplify_context = context or {}
        simplify_context['target_level'] = target_level
        
        # Build prompt using user_prompt (always provided or default)
        prompt = self._build_prompt(
            action_type='simplify',
            block_content=block_content,
            block_type=block_type,
            context=simplify_context,
            user_prompt_text=user_prompt
        )
        
        try:
            response = self.gemini_service.generate(
                system_instruction=system_instruction,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return {
                'simplified_content': response['raw'],
                'model': response['model']
            }
        except Exception as e:
            logger.error(f"Error in simplify: {e}", exc_info=True)
            raise
    
    def summarize(
        self,
        block_content: str,
        block_type: str = "text",
        context: Optional[Dict[str, Any]] = None,
        user_prompt: Optional[str] = None,
        length: str = "brief",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a concise summary of block content.
        
        Args:
            block_content: The content of the block to summarize
            block_type: Type of block (text, code, image, diagram)
            context: Optional context dictionary
            user_prompt: User prompt (sent from frontend, or None to use default)
            length: Summary length ("brief", "medium", "detailed")
            temperature: Temperature for generation (0.0-1.0, default: 0.7)
            max_tokens: Maximum tokens in response (optional)
            
        Returns:
            Dictionary with:
            - 'summary': Summary text
            - 'model': Model name used
        """
        if not block_content or not block_content.strip():
            raise ValueError("block_content is required")
        
        # Get system instruction from database (admin-managed)
        system_instruction = self._get_system_instruction('summarize')
        
        # Use default prompt if not provided
        if not user_prompt:
            user_prompt = self._get_default_user_prompt('summarize')
        
        # Build context with length
        summarize_context = context or {}
        summarize_context['length'] = length
        
        # Build prompt using user_prompt (always provided or default)
        prompt = self._build_prompt(
            action_type='summarize',
            block_content=block_content,
            block_type=block_type,
            context=summarize_context,
            user_prompt_text=user_prompt
        )
        
        try:
            response = self.gemini_service.generate(
                system_instruction=system_instruction,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return {
                'summary': response['raw'],
                'model': response['model']
            }
        except Exception as e:
            logger.error(f"Error in summarize: {e}", exc_info=True)
            raise
    
    def generate_questions(
        self,
        block_content: str,
        block_type: str = "text",
        context: Optional[Dict[str, Any]] = None,
        user_prompt: Optional[str] = None,
        num_questions: int = 3,
        question_types: Optional[List[str]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate questions based on block content.
        
        Args:
            block_content: The content of the block
            block_type: Type of block (text, code, image, diagram)
            context: Optional context dictionary
            user_prompt: User prompt (sent from frontend, or None to use default)
            num_questions: Number of questions to generate (default: 3)
            question_types: Optional list of question types (e.g., ["multiple_choice", "short_answer"])
            temperature: Temperature for generation (0.0-1.0, default: 0.7)
            max_tokens: Maximum tokens in response (optional)
            
        Returns:
            Dictionary with:
            - 'questions': List of question dictionaries
            - 'model': Model name used
        """
        if not block_content or not block_content.strip():
            raise ValueError("block_content is required")
        
        if num_questions < 1 or num_questions > 10:
            raise ValueError("num_questions must be between 1 and 10")
        
        # Get system instruction from database (admin-managed)
        system_instruction = self._get_system_instruction('generate_questions')
        
        # Use default prompt if not provided
        if not user_prompt:
            user_prompt = self._get_default_user_prompt('generate_questions')
        
        # Build context with question-specific parameters
        question_context = context or {}
        question_context['num_questions'] = num_questions
        if question_types:
            question_context['question_types'] = ', '.join(question_types)
        else:
            question_context['question_types'] = 'Mix of multiple choice, short answer, and comprehension questions'
        
        # Build prompt using user_prompt (always provided or default)
        prompt = self._build_prompt(
            action_type='generate_questions',
            block_content=block_content,
            block_type=block_type,
            context=question_context,
            user_prompt_text=user_prompt
        )
        
        # Use shared schema from tutorx.schemas for consistency
        from tutorx.schemas import get_block_generate_questions_schema
        response_schema = get_block_generate_questions_schema()

        try:
            response = self.gemini_service.generate(
                system_instruction=system_instruction,
                prompt=prompt,
                response_schema=response_schema,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            questions = response.get('parsed', [])
            if not questions:
                # Fallback: try to parse from raw response
                logger.warning("Failed to parse structured questions, using raw response")
                questions = [{"question": response['raw'], "type": "unknown", "difficulty": "medium"}]
            
            return {
                'questions': questions[:num_questions],
                'model': response['model']
            }
        except Exception as e:
            logger.error(f"Error in generate_questions: {e}", exc_info=True)
            raise

    def ask_student(
        self,
        lesson_title: str,
        current_sentence: str,
        selected_text: str,
        question: str,
        context_before: Optional[str] = None,
        action_type: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Student Ask AI: answer a student's question using sentence-based context.
        Does not use block_content; builds prompt from lesson_title, context_before,
        current_sentence, selected_text, and question.

        Returns:
            Dictionary with 'answer' and 'model'.
        """
        valid_action_types = [
            'explain_more', 'give_examples', 'simplify', 'summarize',
            'generate_questions', 'harder_questions',
        ]
        if action_type and action_type in valid_action_types:
            # Use generate_questions system instruction for harder_questions (same intent, different schema)
            si_action = 'generate_questions' if action_type == 'harder_questions' else action_type
            system_instruction = self._get_system_instruction(si_action)
        else:
            system_instruction = (
                "You are a helpful tutor. Answer the student's question clearly and concisely "
                "based only on the given context. Be educational and supportive."
            )

        parts = [
            f"Lesson: {lesson_title}",
            "",
            "Current sentence (from the lesson):",
            current_sentence,
            "",
            "Selected text (what the student highlighted):",
            selected_text,
            "",
            "Student's question:",
            question,
        ]
        if context_before and context_before.strip():
            parts.insert(2, "Context (previous sentences):")
            parts.insert(3, context_before.strip())
            parts.insert(4, "")
        prompt = "\n".join(parts)

        # Structured output: use TutorX schemas for question-generation actions
        response_schema = None
        if action_type == 'generate_questions':
            from tutorx.schemas import get_student_generate_questions_schema
            response_schema = get_student_generate_questions_schema()
        elif action_type == 'harder_questions':
            from tutorx.schemas import get_student_harder_questions_schema
            response_schema = get_student_harder_questions_schema()

        try:
            response = self.gemini_service.generate(
                system_instruction=system_instruction,
                prompt=prompt,
                response_schema=response_schema,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            raw = response['raw']
            model = response.get('model')
            parsed = response.get('parsed')

            if action_type == 'generate_questions' and parsed:
                return {
                    'questions': parsed.get('questions', []),
                    'message': parsed.get('message', ''),
                    'model': model,
                }
            if action_type == 'harder_questions' and parsed:
                return {
                    'questions': parsed.get('questions', []),
                    'model': model,
                }
            # All other action types: plain answer
            return {
                'answer': raw,
                'model': model,
            }
        except Exception as e:
            logger.error(f"Error in ask_student: {e}", exc_info=True)
            raise

    def generate_questions_for_lesson_chat(
        self,
        lesson_context: str,
        user_message: str = "",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Lesson chat: generate quiz-style questions from full lesson context.
        Uses same system instruction and schema as Student Ask generate_questions.
        Returns dict with 'questions' (list) and 'message' (str) for response_type qanda.
        """
        if not lesson_context or not lesson_context.strip():
            raise ValueError("lesson_context is required")
        from tutorx.schemas import get_student_generate_questions_schema

        system_instruction = self._get_system_instruction("generate_questions")
        prompt_parts = [lesson_context.strip(), ""]
        if user_message and user_message.strip():
            prompt_parts.append("Student request:")
            prompt_parts.append(user_message.strip())
        else:
            prompt_parts.append("Generate quiz-style questions (multiple choice and true/false) based on the lesson content above. Include a brief closing message (e.g. offering more or harder questions, or asking if they need anything else).")
        prompt = "\n".join(prompt_parts)

        response_schema = get_student_generate_questions_schema()
        response = self.gemini_service.generate(
            system_instruction=system_instruction,
            prompt=prompt,
            response_schema=response_schema,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        parsed = response.get("parsed")
        if not parsed:
            raise ValueError("Failed to parse generate_questions response")
        return {
            "questions": parsed.get("questions", []),
            "message": (parsed.get("message") or "Want to try more questions?").strip() or "Anything else I can help with?",
        }

    def explain_for_lesson_chat(
        self,
        lesson_context: str,
        phrase_or_concept: str,
        user_message: str = "",
        temperature: float = 0.5,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Lesson chat: explain a phrase or concept from the lesson in simpler terms.
        Uses explain_more system instruction; returns plain text (no structured schema).
        """
        if not lesson_context or not lesson_context.strip():
            raise ValueError("lesson_context is required")
        system_instruction = self._get_system_instruction("explain_more")
        prompt_parts = [
            lesson_context.strip(),
            "",
            "The student wants the following explained more simply or at a different level:",
            phrase_or_concept or "(the whole lesson or their question)",
            "",
        ]
        if user_message and user_message.strip():
            prompt_parts.append("Student's full message:")
            prompt_parts.append(user_message.strip())
        prompt = "\n".join(prompt_parts)
        response = self.gemini_service.generate(
            system_instruction=system_instruction,
            prompt=prompt,
            response_schema=None,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (response.get("raw") or "").strip()

