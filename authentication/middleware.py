from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from firebase_admin import auth
import firebase_admin
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class FirebaseAuthenticationMiddleware(MiddlewareMixin):
    """
    Middleware to handle Firebase authentication for specific endpoints.
    
    This middleware can be used to protect specific routes or provide
    additional Firebase-specific functionality.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        """
        Process the request before it reaches the view.
        
        This can be used for additional Firebase-specific processing,
        logging, or route protection.
        """
        # Firebase is already initialized in settings.py
        
        # Add Firebase user info to request if available
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            try:
                # Decode token and add Firebase user info to request
                decoded_token = auth.verify_id_token(token)
                request.firebase_user = decoded_token
                
                # Log authentication for debugging
                logger.debug(f"Firebase user authenticated: {decoded_token.get('email')}")
                
            except auth.InvalidIdTokenError:
                # Don't fail here - let the authentication class handle it
                request.firebase_user = None
            except Exception as e:
                logger.error(f"Middleware authentication error: {e}")
                request.firebase_user = None
        else:
            request.firebase_user = None
        
        return None
    
    def process_response(self, request, response):
        """
        Process the response before it's sent to the client.
        """
        # Add CORS headers if needed
        if hasattr(request, 'firebase_user') and request.firebase_user:
            response['X-Firebase-User'] = request.firebase_user.get('email', '')
        
        return response
