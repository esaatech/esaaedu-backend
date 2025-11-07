"""
WebSocket URL routing for Django Channels
"""
from django.urls import re_path
from .consumers import CourseGenerationConsumer, CourseManagementConsumer

websocket_urlpatterns = [
    re_path(r'^ws/ai/course-generation/$', CourseGenerationConsumer.as_asgi()),
    re_path(r'^ws/ai/course-management/(?P<course_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/$', CourseManagementConsumer.as_asgi()),
]
