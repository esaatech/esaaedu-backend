from django.contrib import admin
from .models import Portfolio, PortfolioItem


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ['student', 'title', 'is_public', 'created_at', 'updated_at']
    list_filter = ['is_public', 'theme', 'created_at']
    search_fields = ['student__email', 'student__public_handle', 'student__first_name', 'student__last_name', 'title']
    readonly_fields = ['created_at', 'updated_at', 'public_url']
    fieldsets = (
        ('Student', {
            'fields': ('student',)
        }),
        ('Portfolio Details', {
            'fields': ('title', 'bio', 'profile_image', 'theme')
        }),
        ('Sections & links', {
            'fields': (
                'projects_section_enabled',
                'linkedin_enabled', 'linkedin_url',
                'github_enabled', 'github_url',
                'instagram_enabled', 'instagram_url',
                'tiktok_enabled', 'tiktok_url',
                'social_other_enabled', 'social_other_label', 'social_other_url',
                'resume_enabled', 'resume_file',
            ),
        }),
        ('Visibility', {
            'fields': ('is_public', 'public_url')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PortfolioItem)
class PortfolioItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'portfolio', 'category', 'featured', 'is_visible', 'order', 'created_at']
    list_filter = ['featured', 'is_visible', 'category', 'created_at']
    search_fields = ['title', 'description', 'portfolio__student__email', 'category']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Relations', {
            'fields': ('portfolio', 'project_submission')
        }),
        ('Content', {
            'fields': ('title', 'description', 'category', 'tags', 'skills_demonstrated')
        }),
        ('Presentation', {
            'fields': ('featured', 'order', 'thumbnail_image', 'demo_url', 'screenshots', 'is_visible')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
