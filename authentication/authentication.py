from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from firebase_admin import auth
import firebase_admin
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

# Initialize Firebase if not already initialized
def ensure_firebase_initialized():
    """Ensure Firebase is initialized before use"""
    if not firebase_admin._apps:
        try:
            from backend.settings import initialize_firebase
            initialize_firebase()
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            return False
    return True


class FirebaseAuthentication(BaseAuthentication):
    """
    Firebase Authentication for Django REST Framework
    
    This authentication class verifies Firebase ID tokens and creates/updates
    Django users based on Firebase user information.
    """
    
    def authenticate(self, request):
        """
        Authenticate the request using Firebase ID token.
        
        Returns:
            tuple: (user, token) if authentication successful, None otherwise
        """
        # Ensure Firebase is initialized
        if not ensure_firebase_initialized():
            return None
            
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        
        if not auth_header:
            return None
            
        try:
            # Extract token from "Bearer <token>" format
            token = self.extract_token(auth_header)
            if not token:
                return None
                
            # Verify the Firebase ID token with retry for clock skew issues
            decoded_token = self._verify_token_with_retry(token)
            
            firebase_uid = decoded_token.get('uid')
            email = decoded_token.get('email')
            
            if not firebase_uid or not email:
                raise AuthenticationFailed('Invalid token: missing required fields')
            
            # Get or create Django user
            user = self.get_or_create_user(decoded_token)
            
            return (user, token)
            
        except auth.InvalidIdTokenError as e:
            logger.warning(f"Invalid Firebase token: {e}")
            raise AuthenticationFailed('Invalid authentication token')
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise AuthenticationFailed('Authentication failed')
    
    def _verify_token_with_retry(self, token, max_retries=2, retry_delay=1):
        """
        Verify Firebase ID token with retry logic for clock skew issues.
        
        Args:
            token: Firebase ID token string
            max_retries: Maximum number of retry attempts (default: 2)
            retry_delay: Delay between retries in seconds (default: 1)
        
        Returns:
            Decoded token dictionary
            
        Raises:
            auth.InvalidIdTokenError: If token is invalid after all retries
            Exception: Other errors
        """
        import time
        
        decoded_token = None
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                # Try to verify token - Firebase Admin SDK handles clock skew internally
                # but we add retry logic for edge cases
                decoded_token = auth.verify_id_token(token, check_revoked=False)
                return decoded_token  # Success
            except auth.InvalidIdTokenError as e:
                error_str = str(e).lower()
                # Check if it's a clock skew error
                if 'too early' in error_str or 'clock' in error_str:
                    if attempt < max_retries:
                        # Wait a bit and retry (gives time for clock sync)
                        logger.warning(f"Clock skew detected, retrying token verification (retry {attempt + 1} of {max_retries})")
                        time.sleep(retry_delay)
                        last_error = e
                        continue
                # Not a clock skew error or out of retries
                raise
            except Exception as e:
                # Other errors, don't retry
                raise
        
        # Should never reach here, but just in case
        if decoded_token is None:
            raise last_error if last_error else Exception("Failed to verify token")
    
    def extract_token(self, auth_header):
        """
        Extract token from Authorization header.
        
        Args:
            auth_header (str): Authorization header value
            
        Returns:
            str: Token if found, None otherwise
        """
        parts = auth_header.split()
        
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return None
            
        return parts[1]
    
    def get_or_create_user(self, decoded_token):
        """
        Get or create Django user from Firebase token data.
        
        Args:
            decoded_token (dict): Decoded Firebase ID token
            
        Returns:
            User: Django user instance
        """
        firebase_uid = decoded_token.get('uid')
        email = decoded_token.get('email')
        name = decoded_token.get('name', '')
        
        try:
            # Try to get existing user by Firebase UID
            user = User.objects.get(firebase_uid=firebase_uid)
            
            # Update user information if changed
            updated = False
            if user.email != email:
                user.email = email
                updated = True
                
            if name and (user.first_name != name.split(' ')[0] if name else ''):
                name_parts = name.split(' ', 1)
                user.first_name = name_parts[0]
                user.last_name = name_parts[1] if len(name_parts) > 1 else ''
                updated = True
                
            if updated:
                user.save()
                
        except User.DoesNotExist:
            # Create new user with STUDENT role as default
            # Note: Teacher signup should happen through dedicated endpoint
            # which will update the role before this authentication is called
            name_parts = name.split(' ', 1) if name else ['', '']
            
            user = User.objects.create_user(
                firebase_uid=firebase_uid,
                email=email,
                first_name=name_parts[0],
                last_name=name_parts[1] if len(name_parts) > 1 else '',
                username=email,  # Use email as username
                role=User.Role.STUDENT  # Explicitly set default role
            )
            
            logger.info(f"Created new user with default student role: {email}")
        
        # Update last login
        from django.utils import timezone
        user.last_login_at = timezone.now()
        user.save(update_fields=['last_login_at'])
        
        return user
    
    def authenticate_header(self, request):
        """
        Return the authentication header for 401 responses.
        """
        return 'Bearer'
