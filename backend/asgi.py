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

    def _normalize_data(self, data):
        """Normalize data that might be a tuple to proper type"""
        if isinstance(data, tuple):
            # Extract first element if tuple
            if len(data) > 0:
                return data[0]
            return b"" if isinstance(data, tuple) else ""
        return data

    async def __call__(self, scope, receive, send):
        # Only wrap WebSocket connections
        if scope["type"] == "websocket":
            # Wrap the receive callable to normalize tuple/bytes data
            async def wrapped_receive():
                try:
                    message = await receive()
                    
                    # Fix Cloud Run's tuple format issue
                    if message and isinstance(message, dict) and message.get("type") == "websocket.receive":
                        # Handle bytes data
                        if "bytes" in message:
                            bytes_data = message["bytes"]
                            try:
                                # Try to normalize tuple data
                                normalized = self._normalize_data(bytes_data)
                                # Ensure it's bytes
                                if isinstance(normalized, bytes):
                                    message["bytes"] = normalized
                                elif normalized:
                                    # Try to convert to bytes
                                    message["bytes"] = bytes(normalized) if not isinstance(normalized, str) else normalized.encode('utf-8')
                                else:
                                    message["bytes"] = b""
                            except Exception as e:
                                logger.error(f"Error normalizing bytes data: {e}, type: {type(bytes_data)}")
                                message["bytes"] = b""
                        
                        # Handle text data
                        if "text" in message:
                            text_data = message["text"]
                            try:
                                # Try to normalize tuple data
                                normalized = self._normalize_data(text_data)
                                # Ensure it's a string
                                if isinstance(normalized, str):
                                    message["text"] = normalized
                                elif normalized:
                                    # Try to convert to string
                                    if isinstance(normalized, bytes):
                                        message["text"] = normalized.decode('utf-8')
                                    else:
                                        message["text"] = str(normalized)
                                else:
                                    message["text"] = ""
                            except Exception as e:
                                logger.error(f"Error normalizing text data: {e}, type: {type(text_data)}")
                                message["text"] = ""
                    
                    return message
                except Exception as e:
                    logger.error(f"Error in wrapped_receive: {e}", exc_info=True)
                    # Return a safe default message
                    return {"type": "websocket.receive", "text": ""}
            
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
