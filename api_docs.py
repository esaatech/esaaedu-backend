"""
API Documentation for EsaaEdu Backend
This file contains the API contract/specification for frontend developers
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json

@require_http_methods(["GET"])
def api_documentation(request):
    """
    API Documentation endpoint
    Returns comprehensive API contract for frontend developers
    """
    
    api_docs = {
        "title": "EsaaEdu API Documentation",
        "version": "1.0.0",
        "description": "API contract for EsaaEdu educational platform",
        "base_url": "https://your-domain.com/api",
        "authentication": {
            "type": "JWT Bearer Token",
            "header": "Authorization: Bearer <token>",
            "login_endpoint": "/api/auth/login/",
            "refresh_endpoint": "/api/auth/refresh/"
        },
        "endpoints": {
            "courses": {
                "create_course": {
                    "method": "POST",
                    "url": "/api/courses/create/",
                    "description": "Create a new course or get creation defaults",
                    "authentication": "Required (Teacher role)",
                    "methods": {
                        "GET": {
                            "description": "Get course creation defaults and categories",
                            "response": {
                                "categories": [
                                    {
                                        "id": "uuid",
                                        "name": "Computer Science",
                                        "description": "Programming, algorithms, data structures..."
                                    }
                                ],
                                "default_settings": {
                                    "max_students_per_course": 30,
                                    "default_course_duration_weeks": 8,
                                    "enable_trial_period": True,
                                    "trial_period_days": 14,
                                    "who_sets_price": "admin"
                                },
                                "form_defaults": {
                                    "max_students": 30,
                                    "duration_weeks": 8,
                                    "price": 0.00,
                                    "is_free": True,
                                    "level": "beginner",
                                    "status": "draft"
                                },
                                "user_can_set_price": False,
                                "user_context": {
                                    "teacher_id": "uuid",
                                    "teacher_name": "John Doe",
                                    "teacher_email": "john@example.com"
                                }
                            }
                        },
                        "POST": {
                            "description": "Create a new course",
                            "request_body": {
                                "title": "string (required)",
                                "description": "string (required)",
                                "long_description": "string",
                                "category": "string (required)",
                                "age_range": "string",
                                "level": "string (beginner|intermediate|advanced)",
                                "price": "decimal (if user can set price)",
                                "is_free": "boolean",
                                "max_students": "integer",
                                "duration_weeks": "integer",
                                "features": "array of strings",
                                "overview": "string",
                                "learning_objectives": "array of strings",
                                "prerequisites_text": "string",
                                "sessions_per_week": "integer",
                                "total_projects": "integer",
                                "value_propositions": "array of strings",
                                "color": "string (hex color)",
                                "icon": "string",
                                "image": "file upload",
                                "schedule": "string",
                                "certificate": "boolean",
                                "status": "string (draft|published)"
                            },
                            "response": {
                                "course": "CourseDetailSerializer data",
                                "billing_setup": "Stripe integration result",
                                "message": "Course created successfully"
                            }
                        }
                    }
                },
                "teacher_courses": {
                    "method": "GET",
                    "url": "/api/courses/teacher/",
                    "description": "List all courses created by authenticated teacher",
                    "authentication": "Required (Teacher role)",
                    "response": "Array of CourseListSerializer data"
                },
                "course_detail": {
                    "method": "GET",
                    "url": "/api/courses/teacher/{course_id}/",
                    "description": "Get detailed course information",
                    "authentication": "Required (Teacher role)",
                    "response": "CourseDetailSerializer data"
                }
            },
            "assessments": {
                "assessment_overview": {
                    "method": "GET",
                    "url": "/api/student/assessments/",
                    "description": "Get comprehensive assessment data",
                    "authentication": "None (Public endpoint)",
                    "response": {
                        "dashboard": "Assessment dashboard counts",
                        "quiz_assessments": "Quiz assessment data",
                        "assignment_assessments": "Assignment assessment data",
                        "instructor_assessments": "Instructor assessment data",
                        "summary": "Assessment summary data"
                    }
                }
            },
            "authentication": {
                "login": {
                    "method": "POST",
                    "url": "/api/auth/login/",
                    "description": "User login",
                    "authentication": "None",
                    "request_body": {
                        "email": "string (required)",
                        "password": "string (required)"
                    },
                    "response": {
                        "access": "JWT access token",
                        "refresh": "JWT refresh token",
                        "user": "User profile data"
                    }
                },
                "refresh": {
                    "method": "POST",
                    "url": "/api/auth/refresh/",
                    "description": "Refresh JWT token",
                    "authentication": "None",
                    "request_body": {
                        "refresh": "string (required)"
                    },
                    "response": {
                        "access": "New JWT access token"
                    }
                }
            }
        },
        "error_responses": {
            "400": "Bad Request - Invalid data",
            "401": "Unauthorized - Invalid or missing token",
            "403": "Forbidden - Insufficient permissions",
            "404": "Not Found - Resource not found",
            "500": "Internal Server Error - Server error"
        },
        "common_headers": {
            "Content-Type": "application/json",
            "Authorization": "Bearer <jwt_token>",
            "Accept": "application/json"
        },
        "data_models": {
            "Course": {
                "id": "UUID",
                "title": "string",
                "description": "string",
                "teacher": "User object",
                "category": "string",
                "price": "decimal",
                "is_free": "boolean",
                "status": "string",
                "created_at": "datetime",
                "updated_at": "datetime"
            },
            "User": {
                "id": "integer",
                "email": "string",
                "first_name": "string",
                "last_name": "string",
                "role": "string (student|teacher|admin)",
                "is_active": "boolean"
            }
        }
    }
    
    return JsonResponse(api_docs, json_dumps_params={'indent': 2})

@require_http_methods(["GET"])
def course_creation_contract(request):
    """
    Specific API contract for course creation
    """
    contract = {
        "endpoint": "/api/courses/create/",
        "description": "Course Creation API Contract",
        "authentication": "JWT Bearer Token (Teacher role required)",
        "methods": {
            "GET": {
                "purpose": "Get course creation defaults and form data",
                "response_structure": {
                    "categories": "Array of available course categories",
                    "default_settings": "System-wide course settings",
                    "form_defaults": "Suggested default values for form fields",
                    "price_control": "Who can set prices (admin/teacher/both)",
                    "user_can_set_price": "Boolean indicating if current user can set prices",
                    "user_context": "Current teacher information"
                }
            },
            "POST": {
                "purpose": "Create a new course",
                "required_fields": ["title", "description", "category"],
                "optional_fields": [
                    "long_description", "age_range", "level", "price", 
                    "is_free", "max_students", "duration_weeks", "features",
                    "overview", "learning_objectives", "prerequisites_text",
                    "sessions_per_week", "total_projects", "value_propositions",
                    "color", "icon", "image", "schedule", "certificate", "status"
                ],
                "price_control_logic": {
                    "admin_only": "Only admin users can set price and is_free fields",
                    "teacher_only": "Only teachers can set price and is_free fields",
                    "both": "Both admin and teachers can set price and is_free fields"
                },
                "response": {
                    "course": "Created course data",
                    "billing_setup": "Stripe integration result",
                    "message": "Success message"
                }
            }
        },
        "example_requests": {
            "GET_example": "GET /api/courses/create/",
            "POST_example": {
                "title": "Introduction to Python Programming",
                "description": "Learn Python basics for beginners",
                "category": "Computer Science",
                "level": "beginner",
                "price": 99.99,
                "is_free": False,
                "max_students": 30,
                "duration_weeks": 8
            }
        }
    }
    
    return JsonResponse(contract, json_dumps_params={'indent': 2})
