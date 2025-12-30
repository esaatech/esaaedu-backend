"""
Django admin for TutorX models
"""
from django.contrib import admin
from .models import TutorXBlockActionConfig, TutorXUserInstructionsDefaults, TutorXBlock


@admin.register(TutorXBlockActionConfig)
class TutorXBlockActionConfigAdmin(admin.ModelAdmin):
    """
    Admin interface for TutorX block action configurations.
    
    Only admins can create/edit these. These are the base system instructions
    that users cannot modify.
    """
    list_display = ['display_name', 'action_type', 'version', 'is_active', 'created_at', 'last_modified_by']
    list_filter = ['is_active', 'action_type', 'created_at']
    search_fields = ['display_name', 'action_type', 'system_instruction', 'default_user_prompt', 'description']
    readonly_fields = ['version', 'created_at', 'updated_at', 'created_by', 'last_modified_by']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('action_type', 'display_name', 'description', 'is_active')
        }),
        ('System Instruction (Admin Only)', {
            'fields': ('system_instruction', 'version'),
            'description': 'This is the base system instruction that cannot be changed by users. Only admins can update this. When you modify the system_instruction, the version will auto-increment.'
        }),
        ('Default User Prompt', {
            'fields': ('default_user_prompt',),
            'description': 'Default user prompt template. Users see this initially and can customize it. Use placeholders: {block_content}, {context}, {num_examples}, {target_level}, etc. This is sent from frontend with each request.'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by', 'last_modified_by'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Track who created/modified the configuration"""
        if not change:  # Creating new
            obj.created_by = request.user
        obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TutorXUserInstructionsDefaults)
class TutorXUserInstructionsDefaultsAdmin(admin.ModelAdmin):
    """
    Admin interface for TutorX user instructions defaults.
    
    Only admins can create/edit these. These are the default user prompts
    that users see initially and can customize.
    """
    list_display = ['display_name', 'action_type', 'version', 'is_active', 'created_at', 'last_modified_by']
    list_filter = ['is_active', 'action_type', 'created_at']
    search_fields = ['display_name', 'action_type', 'default_user_instruction', 'description']
    readonly_fields = ['version', 'created_at', 'updated_at', 'created_by', 'last_modified_by']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('action_type', 'display_name', 'description', 'is_active')
        }),
        ('Default User Instruction (Admin Only)', {
            'fields': ('default_user_instruction', 'version'),
            'description': 'This is the default user instruction that users see initially. Users can customize this through their settings. When you modify the default_user_instruction, the version will auto-increment. Use placeholders: {block_content}, {context}, {num_examples}, {target_level}, etc.'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by', 'last_modified_by'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Track who created/modified the default"""
        if not change:  # Creating new
            obj.created_by = request.user
        obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TutorXBlock)
class TutorXBlockAdmin(admin.ModelAdmin):
    """
    Admin interface for TutorX blocks.
    
    Blocks are content units within TutorX lessons. Each block can be of type:
    text, code, image, or diagram.
    """
    list_display = ['lesson', 'order', 'block_type', 'content_preview', 'created_at', 'updated_at']
    list_filter = ['block_type', 'created_at', 'updated_at']
    search_fields = ['lesson__title', 'content', 'lesson__course__title']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('lesson', 'block_type', 'order')
        }),
        ('Content', {
            'fields': ('content',),
            'description': 'Block content. For code blocks, enter the code. For text blocks, enter the text content.'
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'description': 'Block-specific metadata as JSON. For code blocks: {"language": "python"}. For images: {"url": "...", "caption": "..."}'
        }),
        ('Timestamps', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def content_preview(self, obj):
        """Show preview of content"""
        if obj.content:
            return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
        return '-'
    content_preview.short_description = 'Content Preview'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        qs = super().get_queryset(request)
        return qs.select_related('lesson', 'lesson__course')
