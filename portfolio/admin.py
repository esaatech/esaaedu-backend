from django.contrib import admin
from .models import Portfolio, PortfolioItem


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ['student', 'title', 'is_public', 'custom_url', 'created_at', 'updated_at']
    list_filter = ['is_public', 'theme', 'created_at']
    search_fields = ['student__email', 'student__first_name', 'student__last_name', 'title', 'custom_url']
    readonly_fields = ['created_at', 'updated_at', 'public_url']
    fieldsets = (
        ('Student', {
            'fields': ('student',)
        }),
        ('Portfolio Details', {
            'fields': ('title', 'bio', 'profile_image', 'theme')
        }),
        ('Visibility', {
            'fields': ('is_public', 'custom_url', 'public_url')
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
            'fields': ('featured', 'order', 'thumbnail_image', 'screenshots', 'is_visible')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
