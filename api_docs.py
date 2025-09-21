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
            "type": "Firebase ID Token",
            "header": "Authorization: Bearer <firebase_id_token>",
            "description": "Firebase authentication token obtained from Firebase Auth",
            "token_verification": "Backend verifies Firebase ID token with Firebase Admin SDK",
            "login_endpoint": "/api/auth/login/",
            "refresh_endpoint": "/api/auth/refresh/",
            "firebase_config": {
                "project_id": "your-firebase-project-id",
                "auth_domain": "your-project.firebaseapp.com"
            },
            "frontend_integration": {
                "sdk": "Firebase Auth SDK",
                "get_token": "firebase.auth().currentUser.getIdToken()",
                "refresh_token": "firebase.auth().currentUser.getIdToken(true)",
                "token_expiry": "1 hour (Firebase default)",
                "auto_refresh": "Firebase SDK handles automatic token refresh"
            }
        },
        "endpoints": {
            "courses": {
                "course_management": {
                    "base_url": "/api/courses/create/",
                    "description": "Complete CRUD operations for course management",
                    "authentication": "Required (Teacher role)",
                    "methods": {
                        "GET": {
                            "url": "/api/courses/create/",
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
                            "url": "/api/courses/create/",
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
                        },
                        "PUT": {
                            "url": "/api/courses/create/{course_id}/",
                            "description": "Update an existing course",
                            "request_body": {
                                "title": "string (optional)",
                                "description": "string (optional)",
                                "long_description": "string (optional)",
                                "category": "string (optional)",
                                "age_range": "string (optional)",
                                "level": "string (beginner|intermediate|advanced) (optional)",
                                "price": "decimal (optional, if user can set price)",
                                "is_free": "boolean (optional, if user can set price)",
                                "max_students": "integer (optional)",
                                "duration_weeks": "integer (optional)",
                                "features": "array of strings (optional)",
                                "overview": "string (optional)",
                                "learning_objectives": "array of strings (optional)",
                                "prerequisites_text": "string (optional)",
                                "sessions_per_week": "integer (optional)",
                                "total_projects": "integer (optional)",
                                "value_propositions": "array of strings (optional)",
                                "color": "string (hex color) (optional)",
                                "icon": "string (optional)",
                                "image": "file upload (optional)",
                                "schedule": "string (optional)",
                                "certificate": "boolean (optional)",
                                "status": "string (draft|published) (optional)"
                            },
                            "response": {
                                "course": "Updated CourseDetailSerializer data",
                                "message": "Course updated successfully"
                            }
                        },
                        "DELETE": {
                            "url": "/api/courses/create/{course_id}/",
                            "description": "Delete a course (only if no enrollments)",
                            "request_body": "None",
                            "response": {
                                "message": "Course deleted successfully",
                                "deleted_course": {
                                    "id": "uuid",
                                    "title": "string",
                                    "teacher": "string"
                                }
                            },
                            "constraints": {
                                "enrollment_check": "Cannot delete course with active enrollments",
                                "ownership": "Only course owner (teacher) can delete"
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
            "home": {
                "contact_overview": {
                    "method": "GET",
                    "url": "/api/home/contact/",
                    "description": "Get complete contact page data including methods, team, FAQs, and hours",
                    "authentication": "None (Public endpoint)",
                    "response": {
                        "contact_methods": [
                            {
                                "id": "uuid",
                                "type": "live_chat|email|phone|whatsapp",
                                "title": "Contact Method Title",
                                "description": "Description of the contact method",
                                "availability": "When this method is available",
                                "response_time": "Expected response time",
                                "action_text": "Button or action text",
                                "action_value": "Email, phone, or URL",
                                "icon": "Icon identifier",
                                "color": "Color theme"
                            }
                        ],
                        "support_team": [
                            {
                                "id": "uuid",
                                "name": "Team Member Name",
                                "title": "Job Title",
                                "responsibilities": "What they help with",
                                "email": "Contact email",
                                "avatar_initials": "Initials for avatar"
                            }
                        ],
                        "faqs": [
                            {
                                "id": "uuid",
                                "question": "Frequently asked question",
                                "answer": "Answer to the question",
                                "category": "Question category"
                            }
                        ],
                        "support_hours": [
                            {
                                "id": "uuid",
                                "period": "Time period (e.g., Mon-Fri)",
                                "hours": "Hours (e.g., 9AM-6PM EST)",
                                "is_emergency": "Boolean - is this emergency service"
                            }
                        ]
                    }
                },
                "contact_form_submit": {
                    "method": "POST",
                    "url": "/api/home/contact/",
                    "description": "Submit contact form with validation",
                    "authentication": "None (Public endpoint)",
                    "request_body": {
                        "first_name": "string (required, min 2 chars)",
                        "last_name": "string (required, min 2 chars)",
                        "email": "string (required, valid email)",
                        "phone_number": "string (optional, min 10 digits)",
                        "subject": "string (required) - general|technical|billing|course_guidance|enrollment|other",
                        "child_age": "string (optional) - 3-5|6-8|9-12|13-15|16-18|adult",
                        "message": "string (required, 10-2000 chars)",
                        "wants_updates": "boolean (optional, default false)"
                    },
                    "response": {
                        "message": "Thank you for your message! We will get back to you soon.",
                        "submission": {
                            "id": "uuid",
                            "first_name": "string",
                            "last_name": "string",
                            "email": "string",
                            "subject": "string",
                            "status": "new",
                            "created_at": "datetime"
                        }
                    }
                },
                "contact_methods": {
                    "method": "GET",
                    "url": "/api/home/contact/methods/",
                    "description": "Get all available contact methods",
                    "authentication": "None (Public endpoint)",
                    "response": "Array of ContactMethod objects"
                },
                "support_team": {
                    "method": "GET",
                    "url": "/api/home/contact/support-team/",
                    "description": "Get support team members",
                    "authentication": "None (Public endpoint)",
                    "response": "Array of SupportTeamMember objects"
                },
                "faqs": {
                    "method": "GET",
                    "url": "/api/home/contact/faqs/",
                    "description": "Get frequently asked questions",
                    "authentication": "None (Public endpoint)",
                    "response": "Array of FAQ objects"
                },
                "support_hours": {
                    "method": "GET",
                    "url": "/api/home/contact/support-hours/",
                    "description": "Get support hours information",
                    "authentication": "None (Public endpoint)",
                    "response": "Array of SupportHours objects"
                },
                "contact_submissions": {
                    "method": "GET",
                    "url": "/api/home/contact/submissions/",
                    "description": "Get all contact form submissions (admin only)",
                    "authentication": "Required (Admin role)",
                    "query_parameters": {
                        "status": "string (optional) - new|in_progress|resolved|closed",
                        "search": "string (optional) - search by name, email, subject"
                    },
                    "response": "Array of ContactSubmission objects"
                },
                "contact_submission_detail": {
                    "method": "PUT",
                    "url": "/api/home/contact/submissions/{submission_id}/",
                    "description": "Update contact submission status (admin only)",
                    "authentication": "Required (Admin role)",
                    "request_body": {
                        "status": "string (optional) - new|in_progress|resolved|closed",
                        "response_notes": "string (optional) - internal notes"
                    },
                    "response": "Updated ContactSubmission object"
                },
                "contact_submission_delete": {
                    "method": "DELETE",
                    "url": "/api/home/contact/submissions/{submission_id}/",
                    "description": "Delete contact submission (admin only)",
                    "authentication": "Required (Admin role)",
                    "response": {
                        "message": "Contact submission deleted successfully"
                    }
                }
            },
            "authentication": {
                "login": {
                    "method": "POST",
                    "url": "/api/auth/login/",
                    "description": "User login with Firebase ID token",
                    "authentication": "None",
                    "request_body": {
                        "id_token": "string (required) - Firebase ID token from client"
                    },
                    "response": {
                        "access": "Firebase ID token (same as input)",
                        "refresh": "Firebase refresh token",
                        "user": "User profile data",
                        "message": "Login successful"
                    },
                    "note": "Frontend should obtain Firebase ID token using Firebase Auth SDK before calling this endpoint"
                },
                "refresh": {
                    "method": "POST",
                    "url": "/api/auth/refresh/",
                    "description": "Refresh Firebase token",
                    "authentication": "None",
                    "request_body": {
                        "refresh_token": "string (required) - Firebase refresh token"
                    },
                    "response": {
                        "access": "New Firebase ID token",
                        "refresh": "New Firebase refresh token"
                    },
                    "note": "Use Firebase Auth SDK to refresh tokens on the client side"
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
            "Authorization": "Bearer <firebase_id_token>",
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
        "description": "Course Management API Contract - Complete CRUD Operations",
        "authentication": "Firebase ID Token (Teacher role required)",
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
                "url": "/api/courses/create/",
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
            },
            "PUT": {
                "purpose": "Update an existing course",
                "url": "/api/courses/create/{course_id}/",
                "required_fields": ["course_id"],
                "optional_fields": [
                    "title", "description", "long_description", "category", 
                    "age_range", "level", "price", "is_free", "max_students", 
                    "duration_weeks", "features", "overview", "learning_objectives", 
                    "prerequisites_text", "sessions_per_week", "total_projects", 
                    "value_propositions", "color", "icon", "image", "schedule", 
                    "certificate", "status"
                ],
                "ownership_check": "Only course owner (teacher) can update",
                "price_control": "Same logic as POST method",
                "stripe_sync": "Updates Stripe product if price/is_free changed",
                "response": {
                    "course": "Updated course data",
                    "message": "Course updated successfully"
                }
            },
            "DELETE": {
                "purpose": "Delete a course",
                "url": "/api/courses/create/{course_id}/",
                "required_fields": ["course_id"],
                "constraints": {
                    "enrollment_check": "Cannot delete if course has active enrollments",
                    "ownership": "Only course owner (teacher) can delete"
                },
                "stripe_cleanup": "Deletes associated Stripe product",
                "response": {
                    "message": "Course deleted successfully",
                    "deleted_course": "Course details before deletion"
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
            },
            "PUT_example": {
                "url": "PUT /api/courses/create/123e4567-e89b-12d3-a456-426614174000/",
                "body": {
                    "title": "Advanced Python Programming",
                    "price": 149.99,
                    "level": "intermediate",
                    "status": "published"
                }
            },
            "DELETE_example": {
                "url": "DELETE /api/courses/create/123e4567-e89b-12d3-a456-426614174000/",
                "body": "None"
            }
        },
        "firebase_integration_examples": {
            "javascript": {
                "get_token": "const token = await firebase.auth().currentUser.getIdToken();",
                "api_call": "fetch('/api/courses/create/', { headers: { 'Authorization': `Bearer ${token}` } })",
                "auto_refresh": "firebase.auth().onAuthStateChanged(async (user) => { if (user) { const token = await user.getIdToken(); } })"
            },
            "react_example": {
                "useEffect": "useEffect(() => { const getToken = async () => { const user = firebase.auth().currentUser; if (user) { const token = await user.getIdToken(); setAuthToken(token); } }; getToken(); }, []);",
                "api_call": "const response = await fetch('/api/courses/create/', { method: 'POST', headers: { 'Authorization': `Bearer ${authToken}`, 'Content-Type': 'application/json' }, body: JSON.stringify(courseData) });"
            }
        }
    }
    
    return JsonResponse(contract, json_dumps_params={'indent': 2})


@require_http_methods(["GET"])
def contact_contract(request):
    """
    Specific API contract for contact functionality
    """
    contract = {
        "endpoint": "/api/home/contact/",
        "description": "Contact Management API Contract - Complete Contact System",
        "authentication": "Firebase ID Token (Admin for submissions management)",
        "methods": {
            "GET": {
                "purpose": "Get complete contact page data",
                "url": "/api/home/contact/",
                "response_structure": {
                    "contact_methods": "Array of available contact methods (Live Chat, Email, Phone, WhatsApp)",
                    "support_team": "Array of support team members with roles and contact info",
                    "faqs": "Array of frequently asked questions with answers",
                    "support_hours": "Array of support hours for different time periods"
                },
                "use_cases": [
                    "Load contact page with all components",
                    "Display contact methods with action buttons",
                    "Show support team member cards",
                    "Render FAQ accordion or list",
                    "Display support hours information"
                ]
            },
            "POST": {
                "purpose": "Submit contact form",
                "url": "/api/home/contact/",
                "required_fields": ["first_name", "last_name", "email", "subject", "message"],
                "optional_fields": [
                    "phone_number", "child_age", "wants_updates"
                ],
                "validation_rules": {
                    "first_name": "Minimum 2 characters, required",
                    "last_name": "Minimum 2 characters, required", 
                    "email": "Valid email format, required",
                    "phone_number": "Minimum 10 digits, optional",
                    "subject": "Must be one of: general, technical, billing, course_guidance, enrollment, other",
                    "child_age": "Must be one of: 3-5, 6-8, 9-12, 13-15, 16-18, adult",
                    "message": "10-2000 characters, required",
                    "wants_updates": "Boolean, defaults to false"
                },
                "response": {
                    "message": "Success message",
                    "submission": "Created submission data with ID and status"
                }
            }
        },
        "individual_endpoints": {
            "contact_methods": {
                "url": "/api/home/contact/methods/",
                "method": "GET",
                "purpose": "Get contact methods only",
                "authentication": "None"
            },
            "support_team": {
                "url": "/api/home/contact/support-team/",
                "method": "GET", 
                "purpose": "Get support team only",
                "authentication": "None"
            },
            "faqs": {
                "url": "/api/home/contact/faqs/",
                "method": "GET",
                "purpose": "Get FAQs only", 
                "authentication": "None"
            },
            "support_hours": {
                "url": "/api/home/contact/support-hours/",
                "method": "GET",
                "purpose": "Get support hours only",
                "authentication": "None"
            },
            "submissions_management": {
                "url": "/api/home/contact/submissions/",
                "methods": ["GET", "PUT", "DELETE"],
                "purpose": "Manage contact submissions (admin only)",
                "authentication": "Required (Admin role)",
                "features": [
                    "List all submissions with filtering",
                    "Update submission status and notes",
                    "Delete submissions",
                    "Search by name, email, subject"
                ]
            }
        },
        "example_requests": {
            "GET_contact_overview": "GET /api/home/contact/",
            "POST_contact_form": {
                "first_name": "John",
                "last_name": "Doe", 
                "email": "john@example.com",
                "phone_number": "(555) 123-4567",
                "subject": "course_guidance",
                "child_age": "6-8",
                "message": "I need help choosing the right programming course for my 7-year-old daughter. She's interested in coding but I'm not sure where to start.",
                "wants_updates": True
            },
            "GET_contact_methods": "GET /api/home/contact/methods/",
            "GET_support_team": "GET /api/home/contact/support-team/",
            "GET_faqs": "GET /api/home/contact/faqs/",
            "GET_support_hours": "GET /api/home/contact/support-hours/"
        },
        "frontend_integration_examples": {
            "javascript": {
                "load_contact_page": "const response = await fetch('/api/home/contact/'); const data = await response.json();",
                "submit_contact_form": "const response = await fetch('/api/home/contact/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(formData) });",
                "load_individual_components": "const methods = await fetch('/api/home/contact/methods/').then(r => r.json());"
            },
            "react_example": {
                "useEffect": "useEffect(() => { const loadContactData = async () => { const response = await fetch('/api/home/contact/'); const data = await response.json(); setContactData(data); }; loadContactData(); }, []);",
                "form_submission": "const handleSubmit = async (formData) => { const response = await fetch('/api/home/contact/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(formData) }); const result = await response.json(); if (response.ok) { setSuccessMessage(result.message); } };"
            }
        },
        "data_models": {
            "ContactMethod": {
                "id": "UUID",
                "type": "live_chat|email|phone|whatsapp",
                "title": "string",
                "description": "string",
                "availability": "string",
                "response_time": "string",
                "action_text": "string",
                "action_value": "string",
                "icon": "string",
                "color": "string"
            },
            "SupportTeamMember": {
                "id": "UUID",
                "name": "string",
                "title": "string", 
                "responsibilities": "string",
                "email": "string",
                "avatar_initials": "string"
            },
            "FAQ": {
                "id": "UUID",
                "question": "string",
                "answer": "string",
                "category": "string"
            },
            "SupportHours": {
                "id": "UUID",
                "period": "string",
                "hours": "string",
                "is_emergency": "boolean"
            },
            "ContactSubmission": {
                "id": "UUID",
                "first_name": "string",
                "last_name": "string",
                "email": "string",
                "phone_number": "string",
                "subject": "string",
                "child_age": "string",
                "message": "string",
                "wants_updates": "boolean",
                "status": "new|in_progress|resolved|closed",
                "created_at": "datetime"
            }
        }
    }
    
    return JsonResponse(contract, json_dumps_params={'indent': 2})


