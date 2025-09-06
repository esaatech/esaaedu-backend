import traceback
import logging
from django.http import JsonResponse

logger = logging.getLogger(__name__)

class DebugMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        print(f"🚨 DEBUG: 500 Error occurred!")
        print(f"🚨 DEBUG: URL: {request.path}")
        print(f"🚨 DEBUG: Method: {request.method}")
        print(f"🚨 DEBUG: Exception: {str(exception)}")
        print(f"🚨 DEBUG: Traceback: {traceback.format_exc()}")
        
        logger.error(f"500 Error on {request.path}: {str(exception)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return JsonResponse({
            "error": "Internal Server Error",
            "message": str(exception),
            "path": request.path,
            "debug": True
        }, status=500)
