"""
WebSocket URL routing for board synchronization
"""
from django.urls import re_path
from .consumers import BoardSyncConsumer

websocket_urlpatterns = [
    re_path(r'^ws/classroom/(?P<classroom_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/board/$', 
            BoardSyncConsumer.as_asgi()),
]

