from django.contrib import admin
from .models import ContactMethod, SupportTeamMember, FAQ, SupportHours, ContactSubmission


@admin.register(ContactMethod)
class ContactMethodAdmin(admin.ModelAdmin):
    list_display = ['title', 'type', 'availability', 'response_time', 'is_active', 'order']
    list_filter = ['type', 'is_active', 'color']
    search_fields = ['title', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['order', 'title']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'type', 'description')
        }),
        ('Contact Details', {
            'fields': ('availability', 'response_time', 'action_text', 'action_value')
        }),
        ('Display Settings', {
            'fields': ('icon', 'color', 'is_active', 'order')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SupportTeamMember)
class SupportTeamMemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'title', 'email', 'is_active', 'order']
    list_filter = ['is_active']
    search_fields = ['name', 'title', 'email']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['order', 'name']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('name', 'title', 'email', 'avatar_initials')
        }),
        ('Role Details', {
            'fields': ('responsibilities',)
        }),
        ('Display Settings', {
            'fields': ('is_active', 'order')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ['question_short', 'category', 'is_active', 'order']
    list_filter = ['category', 'is_active']
    search_fields = ['question', 'answer', 'category']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['order', 'question']
    
    def question_short(self, obj):
        return obj.question[:50] + "..." if len(obj.question) > 50 else obj.question
    question_short.short_description = 'Question'
    
    fieldsets = (
        ('FAQ Content', {
            'fields': ('question', 'answer', 'category')
        }),
        ('Display Settings', {
            'fields': ('is_active', 'order')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SupportHours)
class SupportHoursAdmin(admin.ModelAdmin):
    list_display = ['period', 'hours', 'is_emergency', 'is_active', 'order']
    list_filter = ['is_emergency', 'is_active']
    search_fields = ['period', 'hours']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['order', 'period']
    
    fieldsets = (
        ('Hours Information', {
            'fields': ('period', 'hours', 'is_emergency')
        }),
        ('Display Settings', {
            'fields': ('is_active', 'order')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ContactSubmission)
class ContactSubmissionAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'subject', 'status', 'created_at', 'responded_at']
    list_filter = ['status', 'subject', 'wants_updates', 'created_at']
    search_fields = ['first_name', 'last_name', 'email', 'message']
    readonly_fields = ['id', 'full_name', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Contact Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone_number')
        }),
        ('Inquiry Details', {
            'fields': ('subject', 'child_age', 'message', 'wants_updates')
        }),
        ('Status & Response', {
            'fields': ('status', 'response_notes', 'responded_at', 'responded_by')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    full_name.short_description = 'Full Name'
    
    actions = ['mark_as_in_progress', 'mark_as_resolved', 'mark_as_closed']
    
    def mark_as_in_progress(self, request, queryset):
        updated = queryset.update(status='in_progress')
        self.message_user(request, f'{updated} submissions marked as in progress.')
    mark_as_in_progress.short_description = "Mark selected as in progress"
    
    def mark_as_resolved(self, request, queryset):
        updated = queryset.update(status='resolved')
        self.message_user(request, f'{updated} submissions marked as resolved.')
    mark_as_resolved.short_description = "Mark selected as resolved"
    
    def mark_as_closed(self, request, queryset):
        updated = queryset.update(status='closed')
        self.message_user(request, f'{updated} submissions marked as closed.')
    mark_as_closed.short_description = "Mark selected as closed"