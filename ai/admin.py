from django.contrib import admin
from .models import AIConversation


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
