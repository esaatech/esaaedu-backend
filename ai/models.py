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
