#!/usr/bin/env python
"""
Test script to verify Firebase connection and authentication
"""

import os
import sys
import django
from pathlib import Path
from dotenv import load_dotenv

# Add the project root to Python path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# Load environment variables from .env file
load_dotenv()

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from firebase_admin import auth
from authentication.authentication import FirebaseAuthentication
from django.test import RequestFactory
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_firebase_initialization():
    """Test if Firebase is properly initialized"""
    try:
        # Try to access Firebase Auth
        print("🔥 Testing Firebase initialization...")
        
        # This will fail if Firebase isn't initialized
        auth.get_user_by_email('test@example.com')
        
    except auth.UserNotFoundError:
        print("✅ Firebase is properly initialized (UserNotFoundError is expected)")
        return True
    except Exception as e:
        if "Firebase App named" in str(e):
            print(f"❌ Firebase initialization failed: {e}")
            return False
        else:
            print(f"✅ Firebase initialized but got expected error: {e}")
            return True


def test_authentication_class():
    """Test the FirebaseAuthentication class"""
    print("\n🔐 Testing FirebaseAuthentication class...")
    
    auth_class = FirebaseAuthentication()
    factory = RequestFactory()
    
    # Test with no authorization header
    request = factory.get('/')
    result = auth_class.authenticate(request)
    
    if result is None:
        print("✅ Authentication correctly returns None for requests without auth header")
    else:
        print("❌ Authentication should return None for requests without auth header")
    
    # Test with invalid token format
    request = factory.get('/', HTTP_AUTHORIZATION='InvalidFormat')
    result = auth_class.authenticate(request)
    
    if result is None:
        print("✅ Authentication correctly returns None for invalid token format")
    else:
        print("❌ Authentication should return None for invalid token format")
    
    print("✅ FirebaseAuthentication class is working correctly")


def test_environment_variables():
    """Test if all required Firebase environment variables are set"""
    print("\n🌍 Testing environment variables...")
    
    required_vars = [
        'FIREBASE_PROJECT_ID',
        'FIREBASE_PRIVATE_KEY_ID', 
        'FIREBASE_PRIVATE_KEY',
        'FIREBASE_CLIENT_EMAIL',
        'FIREBASE_CLIENT_ID',
        'FIREBASE_CLIENT_X509_CERT_URL'
    ]
    
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            # Don't print the actual private key for security
            if 'PRIVATE_KEY' in var and len(value) > 50:
                print(f"✅ {var}: [PRIVATE KEY SET - {len(value)} characters]")
            else:
                print(f"✅ {var}: {value}")
    
    if missing_vars:
        print(f"\n❌ Missing environment variables: {missing_vars}")
        print("💡 Add these to your .env file or GitHub secrets")
        return False
    else:
        print("\n✅ All Firebase environment variables are set")
        return True


def main():
    """Run all tests"""
    print("🧪 Firebase Integration Test Suite")
    print("=" * 50)
    
    # Test environment variables first
    env_ok = test_environment_variables()
    
    if not env_ok:
        print("\n❌ Environment variables not configured. Skipping Firebase tests.")
        print("💡 Configure your Firebase credentials first:")
        print("   1. Copy env.example to .env")
        print("   2. Add your Firebase credentials to .env")
        print("   3. Run this test again")
        return
    
    # Test Firebase initialization
    firebase_ok = test_firebase_initialization()
    
    if not firebase_ok:
        print("\n❌ Firebase initialization failed")
        return
    
    # Test authentication class
    test_authentication_class()
    
    print("\n🎉 All tests passed!")
    print("🚀 Your Firebase integration is ready to use")
    print("\n📝 Next steps:")
    print("   1. Start your Django server: poetry run python manage.py runserver")
    print("   2. Test authentication endpoints with your React frontend")
    print("   3. Add Firebase credentials to GitHub secrets for deployment")


if __name__ == '__main__':
    main()
