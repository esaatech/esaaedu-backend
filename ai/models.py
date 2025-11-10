"""
AI models for storing conversation history and generation metadata
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid
import json

User = get_user_model()


class AIConversation(models.Model):
    """
    Stores AI conversation history for iterative refinement
    """
    CONVERSATION_TYPES = [
        ('course_generation', 'Course Generation'),
        ('lesson_content', 'Lesson Content'),
        ('quiz_questions', 'Quiz Questions'),
        ('assignment_questions', 'Assignment Questions'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_conversations')
    conversation_type = models.CharField(max_length=50, choices=CONVERSATION_TYPES)
    
    # Context for the conversation (e.g., course_id, lesson_id)
    context = models.JSONField(default=dict, blank=True, help_text="Additional context like course_id, lesson_id, etc.")
    
    # Messages stored as JSON array
    # Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    messages = models.JSONField(default=list, blank=True, help_text="Conversation messages array")
    
    # Final generated content (structured JSON matching expected schema)
    generated_content = models.JSONField(default=dict, blank=True, null=True, help_text="Final structured output from AI")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, help_text="Whether conversation is still active")
    
    class Meta:
        verbose_name = "AI Conversation"
        verbose_name_plural = "AI Conversations"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'conversation_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.get_conversation_type_display()} - {self.created_at.strftime('%Y-%m-%d')}"
    
    def add_message(self, role: str, content: str):
        """Helper method to add a message to the conversation"""
        if not isinstance(self.messages, list):
            self.messages = []
        
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": timezone.now().isoformat()
        })
        self.save()
    
    def get_message_history(self) -> list:
        """Returns message history formatted for AI prompt"""
        return self.messages or []


class AIPrompt(models.Model):
    """
    Stores AI prompts and schemas that can be edited from Django admin
    """
    PROMPT_TYPES = [
        ('course_generation', 'Course Generation'),
        ('lesson_content', 'Lesson Content'),
        ('quiz_questions', 'Quiz Questions'),
        ('assignment_questions', 'Assignment Questions'),
    ]
    
    prompt_type = models.CharField(
        max_length=50,
        choices=PROMPT_TYPES,
        unique=True,
        help_text="Type of prompt (one per type)"
    )
    
    # System instruction for the AI model
    system_instruction = models.TextField(
        help_text="System-level instruction for the AI model (e.g., 'You are an expert educational content creator...')"
    )
    
    # Prompt template (can include placeholders like {user_request}, {context})
    prompt_template = models.TextField(
        help_text="Prompt template. Use placeholders: {user_request}, {context}, {age_range}, {level}, etc."
    )
    
    # Output schema as JSON
    output_schema = models.JSONField(
        help_text="Expected output schema as JSON (e.g., {'type': 'object', 'properties': {...}})"
    )
    
    # Schema description (human-readable)
    schema_description = models.TextField(
        blank=True,
        help_text="Human-readable description of what the schema expects"
    )
    
    # Is this prompt active?
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this prompt is currently active"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_prompts',
        help_text="User who created this prompt"
    )
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_prompts',
        help_text="User who last modified this prompt"
    )
    
    class Meta:
        verbose_name = "AI Prompt"
        verbose_name_plural = "AI Prompts"
        ordering = ['prompt_type']
    
    def __str__(self):
        return f"{self.get_prompt_type_display()} ({'Active' if self.is_active else 'Inactive'})"
    
    def format_prompt(self, user_request: str, context: dict = None) -> str:
        """
        Format the prompt template with user request and context.
        
        Args:
            user_request: User's natural language request
            context: Optional context dictionary
        
        Returns:
            Formatted prompt string
        """
        # Import here to avoid circular imports
        from .prompts import format_categories_list
        
        # Build context string if provided
        context_str = ""
        if context:
            parts = []
            for key, value in context.items():
                if value and key != 'available_categories_list':  # Skip categories list, handle separately
                    parts.append(f"{key}: {value}")
            
            if parts:
                context_str = "\n\nAdditional context:\n" + "\n".join(f"- {part}" for part in parts)
        
        # Format categories list (fetched from database at runtime)
        categories_list = context.get('available_categories_list') if context else None
        if not categories_list:
            categories_list = format_categories_list()
        
        # Format the prompt template
        # Try to format with all placeholders, gracefully handle missing ones
        try:
            formatted = self.prompt_template.format(
                user_request=user_request,
                context=context_str if context else "",
                available_categories_list=categories_list,
                **{k: v for k, v in (context or {}).items() if v and k != 'available_categories_list'}
            )
        except KeyError as e:
            # If template doesn't have a placeholder, just format what we have
            formatted = self.prompt_template.format(
                user_request=user_request,
                context=context_str if context else "",
                **{k: v for k, v in (context or {}).items() if v}
            )
        
        return formatted


class AIPromptTemplate(models.Model):
    """
    Template for AI prompts with default values and configuration.
    Each template represents a type of AI generation (quiz, assignment, etc.)
    """
    # Basic Info (dynamic name, no hardcoded choices)
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique identifier (e.g., 'quiz_generation', 'assignment_generation', 'course_introduction')"
    )
    display_name = models.CharField(
        max_length=200,
        help_text="Human-readable name (e.g., 'Quiz Generation', 'Assignment Generation')"
    )
    description = models.TextField(
        blank=True,
        help_text="What this template is used for"
    )
    
    # Default System Instruction (shown to teachers, can be overridden)
    default_system_instruction = models.TextField(
        help_text="Default system instruction shown to teachers. They can override this."
    )
    
    # AI Configuration (from template, not overridable by teachers)
    model_name = models.CharField(
        max_length=100,
        default='gemini-2.0-flash-001',
        help_text="Gemini model to use"
    )
    temperature = models.FloatField(
        default=0.7,
        help_text="Default temperature (0.0-1.0)"
    )
    max_tokens = models.IntegerField(
        null=True,
        blank=True,
        help_text="Max tokens (null = use model's default)"
    )
    
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this template is currently active"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_prompt_templates',
        help_text="User who created this template"
    )
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_prompt_templates',
        help_text="User who last modified this template"
    )
    
    class Meta:
        verbose_name = "AI Prompt Template"
        verbose_name_plural = "AI Prompt Templates"
        ordering = ['display_name']
    
    def __str__(self):
        return f"{self.display_name} ({'Active' if self.is_active else 'Inactive'})"
