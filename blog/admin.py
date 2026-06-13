from django.contrib import admin
from .models import BlogCategory, Post


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'slug']


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'status', 'author', 'published_at', 'created_at']
    list_filter = ['status', 'categories']
    prepopulated_fields = {'slug': ('title',)}
    raw_id_fields = ['author']
    search_fields = ['title', 'content']
    filter_horizontal = ['categories']
