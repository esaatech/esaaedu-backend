"""
TutorX models for block-based content and AI actions
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Max
import uuid

User = get_user_model()


class TutorXBlockActionConfig(models.Model):
    """
    Configuration for TutorX block actions (admin-only).
    
    Stores system instructions for each action type (explain_more, give_examples, etc.).
    These are base prompts that cannot be changed by users - only admins can update them.
    """
    ACTION_TYPES = [
        ('explain_more', 'Explain More'),
        ('give_examples', 'Give Examples'),
        ('simplify', 'Simplify'),
        ('summarize', 'Summarize'),
        ('generate_questions', 'Generate Questions'),
        ('draw_explainer_image', 'Draw Explainer Image'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action_type = models.CharField(
        max_length=50,
        choices=ACTION_TYPES,
        unique=True,
        help_text="Type of block action"
    )
    display_name = models.CharField(
        max_length=200,
        help_text="Human-readable name for this action"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of what this action does"
    )
    
    # System Instruction (Admin-only, base prompt)
    system_instruction = models.TextField(
        help_text="Base system instruction for this action. This is the foundation prompt that cannot be changed by users. Only admins can update this."
    )
    
    # Default User Prompt (shown to users, can be customized)
    default_user_prompt = models.TextField(
        blank=True,
        default="",
        help_text="Default user prompt template. Users see this initially and can customize it. Use placeholders: {block_content}, {context}, etc."
    )
    
    # Version tracking (similar to SystemInstruction in AI app)
    version = models.IntegerField(
        default=1,
        help_text="Version number (auto-increments when updated)"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this configuration is currently active"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tutorx_configs',
        help_text="Admin who created this configuration"
    )
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_tutorx_configs',
        help_text="Admin who last modified this configuration"
    )
    
    class Meta:
        verbose_name = "TutorX Block Action Config"
        verbose_name_plural = "TutorX Block Action Configs"
        ordering = ['action_type']
        indexes = [
            models.Index(fields=['action_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.display_name} ({self.action_type}) - v{self.version}"
    
    def save(self, *args, **kwargs):
        """Auto-increment version when system_instruction changes"""
        if self.pk:
            # Check if system_instruction changed
            try:
                old_instance = TutorXBlockActionConfig.objects.get(pk=self.pk)
                if old_instance.system_instruction != self.system_instruction:
                    # Increment version
                    max_version = TutorXBlockActionConfig.objects.filter(
                        action_type=self.action_type
                    ).aggregate(Max('version'))['version__max']
                    self.version = (max_version or 0) + 1
            except TutorXBlockActionConfig.DoesNotExist:
                pass
        
        # If this is being set as active, deactivate other versions of same action_type
        if self.is_active:
            TutorXBlockActionConfig.objects.filter(
                action_type=self.action_type
            ).exclude(pk=self.pk).update(is_active=False)
        
        super().save(*args, **kwargs)


class TutorXUserInstructionsDefaults(models.Model):
    """
    Default user instructions for TutorX block actions (admin-managed).
    
    Stores default user prompts that are shown to users initially.
    Users can customize these through UserTutorXInstruction in the settings app.
    These defaults are managed by admins only.
    """
    ACTION_TYPES = [
        ('explain_more', 'Explain More'),
        ('give_examples', 'Give Examples'),
        ('simplify', 'Simplify'),
        ('summarize', 'Summarize'),
        ('generate_questions', 'Generate Questions'),
        ('draw_explainer_image', 'Draw Explainer Image'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action_type = models.CharField(
        max_length=50,
        choices=ACTION_TYPES,
        unique=True,
        help_text="Type of block action"
    )
    display_name = models.CharField(
        max_length=200,
        help_text="Human-readable name for this action"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of what this action does"
    )
    
    # Default User Instruction (admin-managed)
    default_user_instruction = models.TextField(
        help_text="Default user instruction template. Users see this initially and can customize it. Use placeholders: {block_content}, {context}, etc."
    )
    
    # Version tracking
    version = models.IntegerField(
        default=1,
        help_text="Version number (auto-increments when default_user_instruction changes)"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this default is currently active"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tutorx_user_instruction_defaults',
        help_text="Admin who created this default"
    )
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_tutorx_user_instruction_defaults',
        help_text="Admin who last modified this default"
    )
    
    class Meta:
        verbose_name = "TutorX User Instructions Default"
        verbose_name_plural = "TutorX User Instructions Defaults"
        ordering = ['action_type']
        indexes = [
            models.Index(fields=['action_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.display_name} ({self.action_type}) - v{self.version}"
    
    def save(self, *args, **kwargs):
        """Auto-increment version when default_user_instruction changes"""
        if self.pk:
            # Check if default_user_instruction changed
            try:
                old_instance = TutorXUserInstructionsDefaults.objects.get(pk=self.pk)
                if old_instance.default_user_instruction != self.default_user_instruction:
                    # Increment version
                    max_version = TutorXUserInstructionsDefaults.objects.filter(
                        action_type=self.action_type
                    ).aggregate(Max('version'))['version__max']
                    self.version = (max_version or 0) + 1
            except TutorXUserInstructionsDefaults.DoesNotExist:
                pass
        
        # If this is being set as active, deactivate other versions of same action_type
        if self.is_active:
            TutorXUserInstructionsDefaults.objects.filter(
                action_type=self.action_type
            ).exclude(pk=self.pk).update(is_active=False)
        
        super().save(*args, **kwargs)


class TutorXBlock(models.Model):
    """
    Content blocks within a TutorX lesson.
    
    Each TutorX lesson contains multiple blocks that can be of different types:
    - text: Rich text content
    - code: Code snippets with syntax highlighting
    - image: Images with captions
    - diagram: Diagrams or visual content
    
    Blocks are ordered within a lesson and can have AI actions performed on them.
    """
    BLOCK_TYPES = [
        ('text', 'Text Block'),
        ('code', 'Code Block'),
        ('image', 'Image Block'),
        ('diagram', 'Diagram Block'),
        ('table', 'Table Block'),
        ('divider', 'Divider Block'),
    ]
    
    # Basic Information
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(
        'courses.Lesson',
        on_delete=models.CASCADE,
        related_name='tutorx_blocks',
        help_text="Lesson this block belongs to"
    )
    
    # Block Content
    block_type = models.CharField(
        max_length=20,
        choices=BLOCK_TYPES,
        help_text="Type of block (text, code, image, diagram)"
    )
    content = models.TextField(
        help_text="Block content. For code blocks, this is the code. For text blocks, this is the text content."
    )
    
    # Ordering
    order = models.IntegerField(
        help_text="Order of this block within the lesson (1, 2, 3, ...)"
    )
    
    # Metadata (for block-specific data)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Block-specific metadata. For code blocks: {'language': 'python'}. For images: {'url': '...', 'caption': '...'}"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "TutorX Block"
        verbose_name_plural = "TutorX Blocks"
        ordering = ['lesson', 'order']
        unique_together = [['lesson', 'order']]
        indexes = [
            models.Index(fields=['lesson', 'order']),
            models.Index(fields=['block_type']),
        ]
    
    def __str__(self):
        return f"{self.lesson.title} - Block {self.order} ({self.get_block_type_display()})"
    
    def get_content_for_ai(self):
        """
        Get formatted content for AI processing.
        
        Returns:
            str: Formatted content based on block type
        """
        if self.block_type == 'code':
            language = self.metadata.get('language', '')
            return f"[Code Block - {language}]\n{self.content}"
        elif self.block_type == 'image':
            caption = self.metadata.get('caption', '')
            return f"[Image: {caption}]\n{self.content}"
        elif self.block_type == 'diagram':
            return f"[Diagram]\n{self.content}"
        else:
            return self.content


class InteractiveVideo(models.Model):
    """
    Interactive video attached to a TutorX lesson.

    Stores a reference to the underlying AudioVideoMaterial (HLS or regular video)
    and serves as the parent for timestamped interactive events.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    lesson = models.OneToOneField(
        'courses.Lesson',
        on_delete=models.CASCADE,
        related_name='interactive_video',
        help_text='TutorX lesson this interactive video belongs to (type=tutorx)',
    )

    audio_video_material = models.ForeignKey(
        'courses.AudioVideoMaterial',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tutorx_interactive_videos',
        help_text='Underlying audio/video material (HLS or normal file)',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Interactive Video (TutorX)'
        verbose_name_plural = 'Interactive Videos (TutorX)'

    def __str__(self) -> str:
        return f"InteractiveVideo for lesson {self.lesson_id}"


class InteractiveEvent(models.Model):
    """
    Timestamped interactive events for TutorX interactive videos.

    Supports multiple choice, yes/no, true/false, and essay-style prompts.
    Content fields (prompt/explanation) are stored as JSON strings so the
    frontend can use BlockNote for rich text, including images.
    """

    EVENT_TYPES = [
        ('pop_quiz', 'Multiple choice'),
        ('yes_no', 'Yes / No'),
        ('true_false', 'True / False'),
        ('essay', 'Essay'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    interactive_video = models.ForeignKey(
        InteractiveVideo,
        on_delete=models.CASCADE,
        related_name='events',
    )

    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    timestamp_seconds = models.PositiveIntegerField()
    title = models.CharField(max_length=255, blank=True)

    # Generic content fields (BlockNote JSON strings)
    prompt = models.TextField(blank=True)
    explanation = models.TextField(blank=True)

    # Multiple choice options
    options = models.JSONField(null=True, blank=True)
    correct_option_index = models.IntegerField(null=True, blank=True)

    # Yes/No-specific labels & feedback
    yes_label = models.CharField(max_length=50, blank=True)
    no_label = models.CharField(max_length=50, blank=True)
    explanation_yes = models.TextField(blank=True)
    explanation_no = models.TextField(blank=True)

    # True/False flag
    correct_answer = models.BooleanField(null=True, blank=True)

    # Essay: model answer / feedback shown to student after they submit
    model_answer = models.TextField(blank=True)

    class Meta:
        ordering = ['timestamp_seconds', 'id']

    def __str__(self) -> str:
        return f"{self.event_type} at {self.timestamp_seconds}s for video {self.interactive_video_id}"

