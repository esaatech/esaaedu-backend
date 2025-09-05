"""
Google Secret Manager utility functions for securely storing and retrieving secrets.
"""
import json
import logging
from typing import Optional, Dict, Any
from google.cloud import secretmanager
from google.api_core import exceptions as gcp_exceptions

logger = logging.getLogger(__name__)

class SecretManagerClient:
    """Client for interacting with Google Secret Manager."""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.client = secretmanager.SecretManagerServiceClient()
    
    def get_secret(self, secret_name: str, version: str = "latest") -> Optional[str]:
        """
        Retrieve a secret from Google Secret Manager.
        
        Args:
            secret_name: Name of the secret (without project path)
            version: Version of the secret (default: "latest")
            
        Returns:
            Secret value as string, or None if not found
        """
        try:
            name = f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
            response = self.client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode("UTF-8")
            logger.info(f"Successfully retrieved secret: {secret_name}")
            return secret_value
        except gcp_exceptions.NotFound:
            logger.warning(f"Secret not found: {secret_name}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving secret {secret_name}: {e}")
            return None
    
    def get_firebase_credentials(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve Firebase credentials from Secret Manager.
        
        Returns:
            Dictionary containing Firebase credentials, or None if not found
        """
        try:
            # Try to get the complete Firebase credentials as JSON
            firebase_creds_json = self.get_secret("firebase-service-account")
            if firebase_creds_json:
                return json.loads(firebase_creds_json)
            
            # Fallback: get individual secrets
            credentials = {}
            secrets = {
                'project_id': 'firebase-project-id',
                'private_key_id': 'firebase-private-key-id', 
                'private_key': 'firebase-private-key',
                'client_email': 'firebase-client-email',
                'client_id': 'firebase-client-id',
                'client_x509_cert_url': 'firebase-client-x509-cert-url'
            }
            
            for key, secret_name in secrets.items():
                value = self.get_secret(secret_name)
                if value:
                    credentials[key] = value
                else:
                    logger.warning(f"Missing Firebase secret: {secret_name}")
                    return None
            
            # Add required fields for Firebase
            credentials.update({
                "type": "service_account",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "universe_domain": "googleapis.com"
            })
            
            return credentials
            
        except Exception as e:
            logger.error(f"Error retrieving Firebase credentials: {e}")
            return None

def get_secret_manager_client(project_id: str) -> Optional[SecretManagerClient]:
    """
    Create a Secret Manager client.
    
    Args:
        project_id: Google Cloud project ID
        
    Returns:
        SecretManagerClient instance, or None if creation fails
    """
    try:
        return SecretManagerClient(project_id)
    except Exception as e:
        logger.error(f"Failed to create Secret Manager client: {e}")
        return None
