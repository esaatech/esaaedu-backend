"""
WSGI config for backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
import sys

print("🚀 DEBUG: Starting Django application...")
print(f"🚀 DEBUG: Python version: {sys.version}")
print(f"🚀 DEBUG: Django settings module: {os.environ.get('DJANGO_SETTINGS_MODULE', 'not set')}")

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

print("🚀 DEBUG: Getting WSGI application...")
application = get_wsgi_application()
print("🚀 DEBUG: WSGI application loaded successfully!")

# Test database connection
try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        print("🚀 DEBUG: Database connection successful!")
except Exception as e:
    print(f"🚀 DEBUG: Database connection failed: {e}")
