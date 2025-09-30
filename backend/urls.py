"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from rest_framework.routers import DefaultRouter
from api_docs import api_documentation, course_creation_contract, contact_contract, landing_page_contract, teacher_project_contract, teacher_assignment_contract, class_events_contract

# Create API router
router = DefaultRouter()

urlpatterns = [
    path("admin/", admin.site.urls),
    
    # API endpoints
    path("api/auth/", include('authentication.urls')),
    path("api/courses/", include('courses.urls')),
    path("api/billing/", include('billings.urls')),
    path("api/student/", include('student.urls')),
    path("api/teacher/", include('teacher.urls')),
    path("api/settings/", include('settings.urls')),
    path("api/home/", include('home.urls')),
    path("api/", include(router.urls)),
    
    # API Documentation
    path("api/docs/", api_documentation, name="api_documentation"),
    path("api/docs/course-creation/", course_creation_contract, name="course_creation_contract"),
    path("api/docs/contact/", contact_contract, name="contact_contract"),
    path("api/docs/landing-page/", landing_page_contract, name="landing_page_contract"),
    path("api/docs/teacher-projects/", teacher_project_contract, name="teacher_project_contract"),
    path("api/docs/teacher-assignments/", teacher_assignment_contract, name="teacher_assignment_contract"),
    path("api/docs/class-events/", class_events_contract, name="class_events_contract"),
    
    # Health check endpoint
    path("health/", lambda request: JsonResponse({"status": "ok"})),
    
    # Root endpoint for testing
    path("", lambda request: JsonResponse({
        "message": "Little Learners Tech API", 
        "status": "running",
        "debug": {
            "database_engine": request.META.get('DJANGO_SETTINGS_MODULE', 'unknown'),
            "environment": request.META.get('ENVIRONMENT', 'unknown')
        }
    })),
    
    # Debug endpoint to test admin access
    path("debug/", lambda request: JsonResponse({
        "message": "Debug endpoint",
        "admin_url": "/admin/",
        "database_engine": request.META.get('DJANGO_SETTINGS_MODULE', 'unknown'),
        "user_authenticated": request.user.is_authenticated if hasattr(request, 'user') else False,
        "static_url": "/static/",
        "media_url": "/media/"
    })),
]

# Import JsonResponse for health check
from django.http import JsonResponse
