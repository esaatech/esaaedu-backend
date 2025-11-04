"""
WebSocket URL routing for Django Channels
"""
from django.urls import re_path
from .consumers import CourseGenerationConsumer

websocket_urlpatterns = [
    re_path(r'ws/ai/course-generation/$', CourseGenerationConsumer.as_asgi()),
]
