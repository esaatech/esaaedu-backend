from django.contrib import admin
from django.utils.html import format_html
from .models import AIConversation, AIPrompt, AIPromptTemplate, SystemInstruction


@admin.register(AIConversation)
class AIConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'conversation_type', 'created_at', 'updated_at', 'is_active']
    list_filter = ['conversation_type', 'is_active', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'conversation_type', 'is_active')
        }),
        ('Context', {
            'fields': ('context',)
        }),
        ('Messages', {
            'fields': ('messages',)
        }),
        ('Generated Content', {
            'fields': ('generated_content',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(AIPrompt)
class AIPromptAdmin(admin.ModelAdmin):
    list_display = ['prompt_type', 'is_active', 'created_at', 'updated_at', 'last_modified_by']
    list_filter = ['is_active', 'prompt_type', 'created_at']
    search_fields = ['prompt_type', 'system_instruction', 'prompt_template']
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'last_modified_by']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('prompt_type', 'is_active')
        }),
        ('Prompt Configuration', {
            'fields': ('system_instruction', 'prompt_template'),
            'description': 'Use placeholders in prompt_template: {user_request}, {context}, {age_range}, {level}, etc.'
        }),
        ('Output Schema', {
            'fields': ('output_schema', 'schema_description'),
            'description': 'Define the JSON schema that the AI should return. Use JSON format.'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by', 'last_modified_by'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Track who created/modified the prompt and invalidate cache"""
        from .prompts import invalidate_prompt_cache
        
        if not change:  # Creating new
            obj.created_by = request.user
        obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)
        
        # Invalidate cache after saving
        invalidate_prompt_cache(obj.prompt_type)


@admin.register(SystemInstruction)
class SystemInstructionAdmin(admin.ModelAdmin):
    list_display = ['name', 'version', 'is_active', 'created_at', 'created_by', 'last_modified_by']
    list_filter = ['is_active', 'name', 'created_at']
    search_fields = ['name', 'content', 'description']
    readonly_fields = ['version', 'created_at', 'updated_at', 'created_by', 'last_modified_by']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'version', 'is_active')
        }),
        ('Content', {
            'fields': ('content', 'description'),
            'description': 'The system instruction text. When saving a new version, the version number will auto-increment.'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by', 'last_modified_by'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Track who created/modified the instruction"""
        if not change:  # Creating new
            obj.created_by = request.user
        obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AIPromptTemplate)
class AIPromptTemplateAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'name', 'model_name', 'temperature', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'model_name', 'created_at']
    search_fields = ['name', 'display_name', 'description', 'system_instruction__content']
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'last_modified_by', 'default_system_instruction']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'display_name', 'description', 'is_active')
        }),
        ('Default System Instruction', {
            'fields': ('system_instruction', 'default_system_instruction'),
            'description': 'Select a versioned system instruction. The default_system_instruction field shows the content for reference (read-only). Teachers can override this when generating content.'
        }),
        ('AI Configuration', {
            'fields': ('model_name', 'temperature', 'max_tokens'),
            'description': 'These values are used by the backend and cannot be overridden by teachers.'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by', 'last_modified_by'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Track who created/modified the template"""
        if not change:  # Creating new
            obj.created_by = request.user
        obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)
