"""
ASGI config for backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
import logging

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

logger = logging.getLogger(__name__)

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# Import routing after Django setup
from ai.routing import websocket_urlpatterns


class CloudRunWebSocketMiddleware:
    """
    Middleware to fix Cloud Run WebSocket frame format issues.
    Cloud Run's proxy sometimes sends WebSocket frames as tuples instead of bytes.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Only wrap WebSocket connections
        if scope["type"] == "websocket":
            # Wrap the receive callable to normalize tuple/bytes data
            async def wrapped_receive():
                message = await receive()
                
                # Fix Cloud Run's tuple format issue
                if message["type"] == "websocket.receive":
                    # Handle bytes data
                    if "bytes" in message:
                        bytes_data = message["bytes"]
                        # If it's a tuple, extract the first element
                        if isinstance(bytes_data, tuple):
                            logger.warning("Received tuple in WebSocket bytes data, normalizing...")
                            message["bytes"] = bytes_data[0] if bytes_data else b""
                        # Ensure it's bytes
                        elif not isinstance(bytes_data, bytes):
                            logger.warning(f"Converting non-bytes data to bytes: {type(bytes_data)}")
                            message["bytes"] = bytes(bytes_data) if bytes_data else b""
                    
                    # Handle text data
                    if "text" in message:
                        text_data = message["text"]
                        # If it's a tuple, extract the first element
                        if isinstance(text_data, tuple):
                            logger.warning("Received tuple in WebSocket text data, normalizing...")
                            message["text"] = text_data[0] if text_data else ""
                        # Ensure it's a string
                        elif not isinstance(text_data, str):
                            logger.warning(f"Converting non-string data to string: {type(text_data)}")
                            message["text"] = str(text_data) if text_data else ""
                
                return message
            
            return await self.app(scope, wrapped_receive, send)
        else:
            # For HTTP, pass through as-is
            return await self.app(scope, receive, send)


# Note: We don't use AuthMiddlewareStack because we handle Firebase auth
# in the consumer's first message, not via Django session auth
application = CloudRunWebSocketMiddleware(
    ProtocolTypeRouter({
        "http": django_asgi_app,
        "websocket": URLRouter(
            websocket_urlpatterns
        ),
    })
)
