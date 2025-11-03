"""
WebSocket URL routing for Django Channels
"""
from django.urls import re_path
# Import consumers will be added as we implement them
# from .consumers import CourseGenerationConsumer, LessonContentConsumer, etc.

websocket_urlpatterns = [
    # WebSocket routes will be added here
    # Example:
    # re_path(r'ws/ai/course-generation/$', CourseGenerationConsumer.as_asgi()),
]
