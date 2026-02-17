from django.contrib import admin
from .models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'status', 'author', 'published_at', 'created_at']
    list_filter = ['status']
    prepopulated_fields = {'slug': ('title',)}
    raw_id_fields = ['author']
    search_fields = ['title', 'content']
