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
                },
                "class_events": {
                    "base_url": "/api/courses/classes/{class_id}/events/",
                    "description": "Complete class event management system - Schedule lessons, projects, breaks, and meetings",
                    "authentication": "Required (Teacher role)",
                    "methods": {
                        "GET": {
                            "url": "/api/courses/classes/{class_id}/events/",
                            "description": "Get all events for a class with available resources",
                            "path_parameters": {
                                "class_id": "uuid (required) - Class identifier"
                            },
                            "response": {
                                "class_id": "uuid",
                                "class_name": "string",
                                "course_id": "uuid",
                                "course_name": "string",
                                "events": [
                                    {
                                        "id": "uuid",
                                        "title": "string",
                                        "description": "string",
                                        "event_type": "lesson|project|meeting|break",
                                        "lesson_type": "text|video|audio|live (for lesson events)",
                                        "start_time": "datetime",
                                        "end_time": "datetime",
                                        "duration_minutes": "integer",
                                        "lesson_title": "string (for lesson events)",
                                        "project_title": "string (for project events)",
                                        "project_platform_name": "string (for project events)",
                                        "meeting_platform": "string (for live lessons)",
                                        "meeting_link": "string (for live lessons)",
                                        "meeting_id": "string (for live lessons)",
                                        "meeting_password": "string (for live lessons)",
                                        "created_at": "datetime",
                                        "updated_at": "datetime"
                                    }
                                ],
                                "available_lessons": [
                                    {
                                        "id": "integer",
                                        "title": "string",
                                        "description": "string",
                                        "type": "text|video|audio|live",
                                        "duration": "integer",
                                        "order": "integer",
                                        "status": "string",
                                        "created_at": "datetime"
                                    }
                                ],
                                "available_projects": [
                                    {
                                        "id": "integer",
                                        "title": "string",
                                        "instructions": "string",
                                        "submission_type": "link|image|video|audio|file|note|code|presentation",
                                        "points": "integer",
                                        "due_at": "datetime (optional)",
                                        "created_at": "datetime"
                                    }
                                ],
                                "available_platforms": [
                                    {
                                        "id": "uuid",
                                        "name": "string",
                                        "display_name": "string",
                                        "description": "string",
                                        "platform_type": "string",
                                        "base_url": "string",
                                        "icon": "string",
                                        "color": "string",
                                        "is_active": "boolean",
                                        "is_featured": "boolean",
                                        "is_free": "boolean",
                                        "min_age": "integer (optional)",
                                        "max_age": "integer (optional)",
                                        "skill_levels": "array of strings",
                                        "capabilities": "array of strings"
                                    }
                                ]
                            },
                            "use_cases": [
                                "Display class schedule/calendar",
                                "Show available resources for creating new events",
                                "Get comprehensive class event data in one API call"
                            ]
                        },
                        "POST": {
                            "url": "/api/courses/classes/{class_id}/events/",
                            "description": "Create a new class event",
                            "path_parameters": {
                                "class_id": "uuid (required) - Class identifier"
                            },
                            "request_body": {
                                "title": "string (required)",
                                "description": "string (optional)",
                                "event_type": "lesson|project|meeting|break (required)",
                                "start_time": "datetime (required)",
                                "end_time": "datetime (required)",
                                "lesson": "integer (required for lesson events)",
                                "project": "integer (required for project events)",
                                "project_platform": "uuid (required for project events)",
                                "lesson_type": "text|video|audio|live (optional)",
                                "meeting_platform": "string (optional for live lessons)",
                                "meeting_link": "string (optional for live lessons)",
                                "meeting_id": "string (optional for live lessons)",
                                "meeting_password": "string (optional for live lessons)"
                            },
                            "response": {
                                "event": "ClassEventDetailSerializer data",
                                "message": "Event created successfully"
                            },
                            "validation_rules": {
                                "lesson_events": "Must specify lesson field",
                                "project_events": "Must specify project and project_platform fields",
                                "time_validation": "end_time must be after start_time",
                                "project_course_match": "Project must belong to the same course as the class"
                            }
                        }
                    },
                    "event_types": {
                        "lesson": {
                            "description": "Scheduled lesson from course curriculum",
                            "required_fields": ["lesson"],
                            "optional_fields": ["lesson_type", "meeting_platform", "meeting_link", "meeting_id", "meeting_password"]
                        },
                        "project": {
                            "description": "Scheduled project work session",
                            "required_fields": ["project", "project_platform"],
                            "optional_fields": []
                        },
                        "meeting": {
                            "description": "General meeting or discussion",
                            "required_fields": [],
                            "optional_fields": ["meeting_platform", "meeting_link", "meeting_id", "meeting_password"]
                        },
                        "break": {
                            "description": "Break time between activities",
                            "required_fields": [],
                            "optional_fields": []
                        }
                    },
                    "platforms": {
                        "description": "Project platforms available for project events",
                        "categories": [
                            "Visual Programming (Scratch, ScratchJr, Blockly)",
                            "Online IDE (Replit, CodePen, JSFiddle)",
                            "Design Tools (Figma, Canva)",
                            "Data Science (Jupyter Notebook, Google Colab)",
                            "Game Development (Unity, Godot)",
                            "Electronics (Arduino IDE, Arduino Create, Tinkercad, Wokwi, Virtual Breadboard)"
                        ],
                        "features": [
                            "Age-appropriate recommendations",
                            "Skill level filtering",
                            "Collaboration support",
                            "File upload capabilities",
                            "Live preview options"
                        ]
                    }
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
            "teacher": {
                "project_management": {
                    "base_url": "/api/teacher/projects/",
                    "description": "Complete project management system for teachers",
                    "authentication": "Required (Teacher role)",
                    "methods": {
                        "GET": {
                            "url": "/api/teacher/projects/",
                            "description": "List all projects for teacher's courses",
                            "query_parameters": {
                                "course_id": "uuid (optional) - Filter by course",
                                "status": "string (optional) - Filter by status",
                                "search": "string (optional) - Search by title, instructions, or course name"
                            },
                            "response": {
                                "projects": [
                                    {
                                        "id": "integer",
                                        "course": "integer",
                                        "course_id": "integer",
                                        "course_title": "string",
                                        "title": "string",
                                        "instructions": "string",
                                        "submission_type": "link|image|video|audio|file|note|code|presentation",
                                        "submission_type_display": "string",
                                        "allowed_file_types": "array of strings",
                                        "points": "integer",
                                        "due_at": "datetime (optional)",
                                        "created_at": "datetime",
                                        "submission_count": "integer",
                                        "graded_count": "integer",
                                        "pending_count": "integer",
                                        "requires_file_upload": "boolean",
                                        "requires_text_input": "boolean",
                                        "requires_url_input": "boolean"
                                    }
                                ],
                                "summary": {
                                    "total_projects": "integer",
                                    "total_submissions": "integer",
                                    "graded_submissions": "integer",
                                    "pending_submissions": "integer",
                                    "grading_completion_rate": "decimal"
                                }
                            }
                        },
                        "POST": {
                            "url": "/api/teacher/projects/",
                            "description": "Create a new project",
                            "request_body": {
                                "course": "uuid (required) - Course ID",
                                "title": "string (required) - Project title",
                                "instructions": "string (required) - Project instructions",
                                "submission_type": "string (required) - link|image|video|audio|file|note|code|presentation",
                                "allowed_file_types": "array of strings (optional) - File extensions",
                                "points": "integer (required) - Maximum points",
                                "due_at": "datetime (optional) - Due date"
                            },
                            "response": {
                                "project": "ProjectSerializer data",
                                "message": "Project created successfully"
                            },
                            "features": [
                                "Automatically creates submissions for all enrolled students",
                                "Validates course ownership",
                                "Supports all submission types"
                            ]
                        },
                        "PUT": {
                            "url": "/api/teacher/projects/{project_id}/",
                            "description": "Update an existing project",
                            "request_body": {
                                "title": "string (optional)",
                                "instructions": "string (optional)",
                                "submission_type": "string (optional)",
                                "allowed_file_types": "array of strings (optional)",
                                "points": "integer (optional)",
                                "due_at": "datetime (optional)"
                            },
                            "response": {
                                "project": "Updated ProjectSerializer data",
                                "message": "Project updated successfully"
                            }
                        },
                        "DELETE": {
                            "url": "/api/teacher/projects/{project_id}/",
                            "description": "Delete a project",
                            "response": {
                                "message": "Project deleted successfully"
                            },
                            "constraints": {
                                "submission_check": "Cannot delete if project has submissions",
                                "ownership": "Only project owner (teacher) can delete"
                            }
                        }
                    }
                },
                "project_grading": {
                    "base_url": "/api/teacher/projects/{project_id}/grading/",
                    "description": "Project submission grading and management",
                    "authentication": "Required (Teacher role)",
                    "methods": {
                        "GET": {
                            "url": "/api/teacher/projects/{project_id}/grading/",
                            "description": "Get all submissions for a specific project",
                            "query_parameters": {
                                "status": "string (optional) - ASSIGNED|SUBMITTED|RETURNED|GRADED",
                                "search": "string (optional) - Search by student name or email"
                            },
                            "response": {
                                "project": "ProjectSerializer data",
                                "submissions": [
                                    {
                                        "id": "integer",
                                        "project": "integer",
                                        "project_id": "integer",
                                        "project_title": "string",
                                        "student": "integer",
                                        "student_name": "string",
                                        "student_email": "string",
                                        "status": "ASSIGNED|SUBMITTED|RETURNED|GRADED",
                                        "status_display": "string",
                                        "content": "string",
                                        "file_url": "string (optional)",
                                        "reflection": "string (optional)",
                                        "submitted_at": "datetime (optional)",
                                        "graded_at": "datetime (optional)",
                                        "grader": "uuid (optional)",
                                        "grader_name": "string (optional)",
                                        "points_earned": "decimal (optional)",
                                        "feedback": "string (optional)",
                                        "feedback_response": "string (optional)",
                                        "feedback_checked": "boolean",
                                        "feedback_checked_at": "datetime (optional)",
                                        "created_at": "datetime",
                                        "updated_at": "datetime"
                                    }
                                ],
                                "grading_stats": {
                                    "total_submissions": "integer",
                                    "graded_count": "integer",
                                    "pending_count": "integer",
                                    "average_score": "decimal",
                                    "grading_progress": "decimal"
                                }
                            }
                        },
                        "PUT": {
                            "url": "/api/teacher/projects/submissions/{submission_id}/",
                            "description": "Grade a project submission",
                            "request_body": {
                                "status": "string (required) - ASSIGNED|SUBMITTED|RETURNED|GRADED",
                                "points_earned": "decimal (optional) - Points awarded",
                                "feedback": "string (optional) - Teacher feedback"
                            },
                            "response": {
                                "submission": "Updated ProjectSubmissionSerializer data",
                                "message": "Submission graded successfully"
                            },
                            "validation": {
                                "status_transitions": "Validates proper status transitions",
                                "points_validation": "Points cannot be negative",
                                "grading_requirements": "GRADED status requires points_earned"
                            }
                        }
                    }
                },
                "submission_detail": {
                    "base_url": "/api/teacher/projects/submissions/{submission_id}/",
                    "description": "Detailed view and feedback for individual submissions",
                    "authentication": "Required (Teacher role)",
                    "methods": {
                        "GET": {
                            "url": "/api/teacher/projects/submissions/{submission_id}/",
                            "description": "Get detailed view of a specific submission",
                            "response": {
                                "submission": "ProjectSubmissionSerializer data",
                                "project": "ProjectSerializer data"
                            }
                        },
                        "POST": {
                            "url": "/api/teacher/projects/submissions/{submission_id}/",
                            "description": "Provide feedback on a submission",
                            "request_body": {
                                "status": "string (required) - RETURNED|GRADED",
                                "feedback": "string (required) - Teacher feedback"
                            },
                            "response": {
                                "submission": "Updated ProjectSubmissionSerializer data",
                                "message": "Feedback provided successfully"
                            }
                        }
                    }
                },
                "project_dashboard": {
                    "base_url": "/api/teacher/projects/dashboard/",
                    "description": "Comprehensive project dashboard for teachers",
                    "authentication": "Required (Teacher role)",
                    "methods": {
                        "GET": {
                            "url": "/api/teacher/projects/dashboard/",
                            "description": "Get comprehensive project dashboard data",
                            "response": {
                                "overview": {
                                    "total_projects": "integer",
                                    "total_submissions": "integer",
                                    "graded_submissions": "integer",
                                    "pending_submissions": "integer",
                                    "overdue_submissions": "integer"
                                },
                                "recent_projects": "Array of recent 5 projects",
                                "pending_grading": "Array of submissions pending grading",
                                "recent_submissions": "Array of recent 10 submissions",
                                "course_projects": [
                                    {
                                        "course_id": "integer",
                                        "course_title": "string",
                                        "project_count": "integer",
                                        "submission_count": "integer",
                                        "graded_count": "integer",
                                        "pending_count": "integer"
                                    }
                                ]
                            }
                        }
                    }
                },
                "assignment_management": {
                    "base_url": "/api/teacher/assignments/",
                    "description": "Complete assignment management system for teachers",
                    "authentication": "Required (Teacher role)",
                    "methods": {
                        "GET": {
                            "url": "/api/teacher/assignments/",
                            "description": "List all assignments for teacher's courses",
                            "query_parameters": {
                                "course_id": "uuid (optional) - Filter by course",
                                "lesson_id": "uuid (optional) - Filter by lesson",
                                "assignment_type": "string (optional) - Filter by type (homework|quiz|exam|project)",
                                "search": "string (optional) - Search by title or description"
                            },
                            "response": {
                                "assignments": [
                                    {
                                        "id": "uuid",
                                        "lesson": "uuid",
                                        "lesson_title": "string",
                                        "course_title": "string",
                                        "title": "string",
                                        "description": "string",
                                        "assignment_type": "homework|quiz|exam|project",
                                        "due_date": "datetime (optional)",
                                        "passing_score": "integer",
                                        "max_attempts": "integer",
                                        "show_correct_answers": "boolean",
                                        "randomize_questions": "boolean",
                                        "created_at": "datetime",
                                        "question_count": "integer",
                                        "submission_count": "integer"
                                    }
                                ],
                                "total_count": "integer"
                            }
                        },
                        "GET_DETAIL": {
                            "url": "/api/teacher/assignments/{assignment_id}/",
                            "description": "Get detailed assignment information with questions",
                            "response": {
                                "assignment": {
                                    "id": "uuid",
                                    "lesson": "uuid",
                                    "lesson_title": "string",
                                    "course_title": "string",
                                    "title": "string",
                                    "description": "string",
                                    "assignment_type": "homework|quiz|exam|project",
                                    "due_date": "datetime (optional)",
                                    "passing_score": "integer",
                                    "max_attempts": "integer",
                                    "show_correct_answers": "boolean",
                                    "randomize_questions": "boolean",
                                    "created_at": "datetime",
                                    "questions": [
                                        {
                                            "id": "uuid",
                                            "question_text": "string",
                                            "type": "multiple_choice|true_false|fill_blank|short_answer|essay|flashcard",
                                            "content": "object - Question-specific content",
                                            "points": "integer",
                                            "order": "integer",
                                            "explanation": "string (optional)"
                                        }
                                    ]
                                }
                            }
                        },
                        "POST": {
                            "url": "/api/teacher/assignments/",
                            "description": "Create a new assignment",
                            "request_body": {
                                "lesson": "uuid (required) - Lesson ID",
                                "title": "string (required) - Assignment title",
                                "description": "string (optional) - Assignment description",
                                "assignment_type": "string (optional) - homework|quiz|exam|project (default: homework)",
                                "due_date": "datetime (optional) - Due date",
                                "passing_score": "integer (optional) - Minimum score to pass (default: 70)",
                                "max_attempts": "integer (optional) - Max attempts allowed (default: 1)",
                                "show_correct_answers": "boolean (optional) - Show answers after completion (default: false)",
                                "randomize_questions": "boolean (optional) - Randomize question order (default: false)"
                            },
                            "response": {
                                "assignment": "AssignmentDetailSerializer data",
                                "message": "Assignment created successfully"
                            },
                            "features": [
                                "Validates lesson ownership",
                                "Supports all assignment types",
                                "Automatic default values for optional fields"
                            ]
                        },
                        "PUT": {
                            "url": "/api/teacher/assignments/{assignment_id}/",
                            "description": "Update an existing assignment",
                            "request_body": {
                                "title": "string (optional)",
                                "description": "string (optional)",
                                "assignment_type": "string (optional)",
                                "due_date": "datetime (optional)",
                                "passing_score": "integer (optional)",
                                "max_attempts": "integer (optional)",
                                "show_correct_answers": "boolean (optional)",
                                "randomize_questions": "boolean (optional)"
                            },
                            "response": {
                                "assignment": "Updated AssignmentDetailSerializer data",
                                "message": "Assignment updated successfully"
                            }
                        },
                        "DELETE": {
                            "url": "/api/teacher/assignments/{assignment_id}/",
                            "description": "Delete an assignment",
                            "response": {
                                "message": "Assignment deleted successfully"
                            },
                            "constraints": {
                                "submission_check": "Cannot delete if assignment has submissions",
                                "ownership": "Only assignment owner (teacher) can delete"
                            }
                        }
                    }
                },
                "assignment_questions": {
                    "base_url": "/api/teacher/assignments/{assignment_id}/questions/",
                    "description": "Assignment question management system",
                    "authentication": "Required (Teacher role)",
                    "methods": {
                        "GET": {
                            "url": "/api/teacher/assignments/{assignment_id}/questions/",
                            "description": "List all questions for an assignment",
                            "response": {
                                "questions": [
                                    {
                                        "id": "uuid",
                                        "question_text": "string",
                                        "type": "multiple_choice|true_false|fill_blank|short_answer|essay|flashcard",
                                        "content": "object - Question-specific content",
                                        "points": "integer",
                                        "order": "integer",
                                        "explanation": "string (optional)",
                                        "created_at": "datetime"
                                    }
                                ]
                            }
                        },
                        "POST": {
                            "url": "/api/teacher/assignments/{assignment_id}/questions/",
                            "description": "Create a new question for an assignment",
                            "request_body": {
                                "question_text": "string (required) - The question text",
                                "type": "string (required) - multiple_choice|true_false|fill_blank|short_answer|essay|flashcard",
                                "content": "object (required) - Question-specific content structure",
                                "points": "integer (required) - Points for this question",
                                "order": "integer (optional) - Question order",
                                "explanation": "string (optional) - Explanation for correct answer"
                            },
                            "content_examples": {
                                "multiple_choice": {
                                    "content": {
                                        "options": ["Option A", "Option B", "Option C", "Option D"],
                                        "correct_answer": "Option B"
                                    }
                                },
                                "true_false": {
                                    "content": {
                                        "correct_answer": true
                                    }
                                },
                                "fill_blank": {
                                    "content": {
                                        "blanks": ["blank1", "blank2"],
                                        "correct_answers": {
                                            "blank1": "answer1",
                                            "blank2": "answer2"
                                        }
                                    }
                                },
                                "short_answer": {
                                    "content": {
                                        "correct_answer": "Expected answer",
                                        "accept_variations": true
                                    }
                                },
                                "essay": {
                                    "content": {
                                        "min_words": 100,
                                        "max_words": 500,
                                        "rubric": "Grading criteria"
                                    }
                                },
                                "flashcard": {
                                    "content": {
                                        "front": "Question side",
                                        "back": "Answer side"
                                    }
                                }
                            },
                            "response": {
                                "question": "AssignmentQuestionSerializer data",
                                "message": "Question created successfully"
                            }
                        },
                        "PUT": {
                            "url": "/api/teacher/assignments/{assignment_id}/questions/{question_id}/",
                            "description": "Update an existing question",
                            "request_body": {
                                "question_text": "string (optional)",
                                "type": "string (optional)",
                                "content": "object (optional)",
                                "points": "integer (optional)",
                                "order": "integer (optional)",
                                "explanation": "string (optional)"
                            },
                            "response": {
                                "question": "Updated AssignmentQuestionSerializer data",
                                "message": "Question updated successfully"
                            }
                        },
                        "DELETE": {
                            "url": "/api/teacher/assignments/{assignment_id}/questions/{question_id}/",
                            "description": "Delete a question",
                            "response": {
                                "message": "Question deleted successfully"
                            },
                            "constraints": {
                                "ownership": "Only assignment owner (teacher) can delete questions"
                            }
                        }
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
                },
                "landing_page": {
                    "method": "GET",
                    "url": "/api/home/",
                    "description": "Get complete landing page data including testimonials, featured courses, and stats",
                    "authentication": "None (Public endpoint)",
                    "response": {
                        "testimonials": [
                            {
                                "id": "string",
                                "rating": "integer (1-5)",
                                "quote": "string - testimonial text",
                                "reviewer_name": "string - Parent of Child (age)",
                                "course_tag": "string - course category",
                                "course_title": "string - course title",
                                "avatar_initials": "string - initials for avatar",
                                "created_at": "datetime - ISO format"
                            }
                        ],
                        "featured_courses": [
                            {
                                "id": "uuid",
                                "title": "string",
                                "description": "string",
                                "category": "string",
                                "level": "string - beginner|intermediate|advanced",
                                "age_range": "string - e.g., Ages 6-10",
                                "price": "decimal",
                                "is_free": "boolean",
                                "duration_weeks": "integer",
                                "enrolled_students_count": "integer",
                                "rating": "decimal - average rating",
                                "image_url": "string - course image URL",
                                "color": "string - CSS color class",
                                "icon": "string - icon name"
                            }
                        ],
                        "stats": {
                            "total_students": "integer",
                            "total_courses": "integer", 
                            "total_reviews": "integer",
                            "average_rating": "decimal",
                            "satisfaction_rate": "integer - percentage"
                        },
                        "hero_section": {
                            "title": "string - main headline",
                            "subtitle": "string - subheading",
                            "cta_text": "string - call-to-action button text",
                            "background_image": "string - hero background image URL"
                        }
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
            },
            "Project": {
                "id": "integer",
                "course": "integer (Course ID)",
                "title": "string",
                "instructions": "string",
                "submission_type": "string (link|image|video|audio|file|note|code|presentation)",
                "allowed_file_types": "array of strings",
                "points": "integer",
                "due_at": "datetime (optional)",
                "created_at": "datetime",
                "submission_count": "integer (computed)",
                "graded_count": "integer (computed)",
                "pending_count": "integer (computed)",
                "requires_file_upload": "boolean (computed)",
                "requires_text_input": "boolean (computed)",
                "requires_url_input": "boolean (computed)"
            },
            "ProjectSubmission": {
                "id": "integer",
                "project": "integer (Project ID)",
                "student": "integer (User ID)",
                "status": "string (ASSIGNED|SUBMITTED|RETURNED|GRADED)",
                "content": "string (optional)",
                "file_url": "string (optional)",
                "reflection": "string (optional)",
                "submitted_at": "datetime (optional)",
                "graded_at": "datetime (optional)",
                "grader": "UUID (User ID, optional)",
                "points_earned": "decimal (optional)",
                "feedback": "string (optional)",
                "feedback_response": "string (optional)",
                "feedback_checked": "boolean",
                "feedback_checked_at": "datetime (optional)",
                "created_at": "datetime",
                "updated_at": "datetime"
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
def landing_page_contract(request):
    """
    Specific API contract for landing page functionality
    """
    contract = {
        "endpoint": "/api/home/",
        "description": "Landing Page API Contract - Complete Homepage Data",
        "authentication": "None (Public endpoint)",
        "methods": {
            "GET": {
                "purpose": "Get complete landing page data",
                "url": "/api/home/",
                "response_structure": {
                    "testimonials": "Array of featured testimonials for 'What People Are Saying' section",
                    "featured_courses": "Array of featured courses for homepage display",
                    "stats": "Landing page statistics and metrics",
                    "hero_section": "Hero section content and configuration"
                },
                "use_cases": [
                    "Load homepage with testimonials",
                    "Display featured courses",
                    "Show platform statistics",
                    "Render hero section content"
                ]
            }
        },
        "testimonials_section": {
            "description": "What People Are Saying section data",
            "data_structure": {
                "id": "string - testimonial ID",
                "rating": "integer (1-5) - star rating",
                "quote": "string - testimonial text content",
                "reviewer_name": "string - formatted as 'Parent of Child (age)'",
                "course_tag": "string - course category for display tag",
                "course_title": "string - course title for context",
                "avatar_initials": "string - initials for avatar display",
                "created_at": "datetime - ISO format timestamp"
            },
            "frontend_integration": {
                "display_format": "Card layout with rating stars, quote, reviewer info, and course tag",
                "avatar_generation": "Use avatar_initials to generate circular avatars",
                "rating_display": "Convert rating integer to star display (1-5 stars)",
                "responsive_design": "Cards should be responsive and scrollable"
            }
        },
        "featured_courses_section": {
            "description": "Featured courses for homepage display",
            "data_structure": {
                "id": "UUID - course identifier",
                "title": "string - course title",
                "description": "string - course description",
                "category": "string - course category",
                "level": "string - beginner|intermediate|advanced",
                "age_range": "string - target age range",
                "price": "decimal - course price",
                "is_free": "boolean - whether course is free",
                "duration_weeks": "integer - course duration",
                "enrolled_students_count": "integer - number of enrolled students",
                "rating": "decimal - average course rating",
                "image_url": "string - course image URL",
                "color": "string - CSS color class",
                "icon": "string - icon name for display"
            }
        },
        "stats_section": {
            "description": "Platform statistics and metrics",
            "data_structure": {
                "total_students": "integer - total number of students",
                "total_courses": "integer - total number of courses",
                "total_reviews": "integer - total number of reviews",
                "average_rating": "decimal - average platform rating",
                "satisfaction_rate": "integer - satisfaction percentage"
            }
        },
        "hero_section": {
            "description": "Hero section content and configuration",
            "data_structure": {
                "title": "string - main headline",
                "subtitle": "string - subheading text",
                "cta_text": "string - call-to-action button text",
                "background_image": "string - hero background image URL"
            }
        },
        "example_requests": {
            "GET_landing_page": "GET /api/home/",
            "response_example": {
                "testimonials": [
                    {
                        "id": "10",
                        "rating": 5,
                        "quote": "Alex went from knowing nothing about coding to building his own game in just 6 weeks! The instructors are amazing and really know how to keep kids engaged.",
                        "reviewer_name": "Sarah M. of Alex (12)",
                        "course_tag": "Game Development",
                        "course_title": "Game Development Course",
                        "avatar_initials": "SM",
                        "created_at": "2025-09-21T15:17:10.094196+00:00"
                    }
                ],
                "featured_courses": [
                    {
                        "id": "23633616-9f19-42eb-8575-71411004ba53",
                        "title": "Python Programming 101",
                        "description": "A beginner-friendly course that teaches the fundamentals of Python programming",
                        "category": "Programming",
                        "level": "beginner",
                        "age_range": "Ages 10-14",
                        "price": 400.0,
                        "is_free": false,
                        "duration_weeks": 8,
                        "enrolled_students_count": 12,
                        "rating": 5.0,
                        "image_url": "/static/images/course-placeholder.jpg",
                        "color": "bg-gradient-primary",
                        "icon": "BookOpen"
                    }
                ],
                "stats": {
                    "total_students": 12,
                    "total_courses": 6,
                    "total_reviews": 12,
                    "average_rating": 4.8,
                    "satisfaction_rate": 98
                },
                "hero_section": {
                    "title": "Empowering Young Minds Through Technology",
                    "subtitle": "Interactive coding courses designed for kids and teens",
                    "cta_text": "Start Learning Today",
                    "background_image": "/static/images/hero-bg.jpg"
                }
            }
        },
        "frontend_integration_examples": {
            "javascript": {
                "load_landing_page": "const response = await fetch('/api/home/'); const data = await response.json();",
                "display_testimonials": "data.testimonials.forEach(testimonial => { /* render testimonial card */ });",
                "display_courses": "data.featured_courses.forEach(course => { /* render course card */ });",
                "display_stats": "document.getElementById('stats').innerHTML = data.stats.total_students;"
            },
            "react_example": {
                "useEffect": "useEffect(() => { const loadLandingData = async () => { const response = await fetch('/api/home/'); const data = await response.json(); setTestimonials(data.testimonials); setCourses(data.featured_courses); setStats(data.stats); }; loadLandingData(); }, []);",
                "testimonial_component": "const TestimonialCard = ({ testimonial }) => ( <div className='testimonial-card'> <div className='stars'>{'★'.repeat(testimonial.rating)}</div> <p>{testimonial.quote}</p> <div className='reviewer'>{testimonial.reviewer_name}</div> <div className='course-tag'>{testimonial.course_tag}</div> </div> );"
            }
        },
        "data_models": {
            "Testimonial": {
                "id": "string",
                "rating": "integer (1-5)",
                "quote": "string",
                "reviewer_name": "string",
                "course_tag": "string",
                "course_title": "string",
                "avatar_initials": "string",
                "created_at": "datetime"
            },
            "FeaturedCourse": {
                "id": "UUID",
                "title": "string",
                "description": "string",
                "category": "string",
                "level": "string",
                "age_range": "string",
                "price": "decimal",
                "is_free": "boolean",
                "duration_weeks": "integer",
                "enrolled_students_count": "integer",
                "rating": "decimal",
                "image_url": "string",
                "color": "string",
                "icon": "string"
            },
            "LandingStats": {
                "total_students": "integer",
                "total_courses": "integer",
                "total_reviews": "integer",
                "average_rating": "decimal",
                "satisfaction_rate": "integer"
            },
            "HeroSection": {
                "title": "string",
                "subtitle": "string",
                "cta_text": "string",
                "background_image": "string"
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
            },
            "Testimonial": {
                "id": "string",
                "rating": "integer (1-5)",
                "quote": "string",
                "reviewer_name": "string",
                "course_tag": "string",
                "course_title": "string",
                "avatar_initials": "string",
                "created_at": "datetime"
            },
            "FeaturedCourse": {
                "id": "UUID",
                "title": "string",
                "description": "string",
                "category": "string",
                "level": "string",
                "age_range": "string",
                "price": "decimal",
                "is_free": "boolean",
                "duration_weeks": "integer",
                "enrolled_students_count": "integer",
                "rating": "decimal",
                "image_url": "string",
                "color": "string",
                "icon": "string"
            },
            "LandingStats": {
                "total_students": "integer",
                "total_courses": "integer",
                "total_reviews": "integer",
                "average_rating": "decimal",
                "satisfaction_rate": "integer"
            },
            "HeroSection": {
                "title": "string",
                "subtitle": "string",
                "cta_text": "string",
                "background_image": "string"
            }
        }
    }
    
    return JsonResponse(contract, json_dumps_params={'indent': 2})




@require_http_methods(["GET"])
def teacher_project_contract(request):
    """
    Specific API contract for teacher project management functionality
    """
    contract = {
        "title": "Teacher Project Management API Contract",
        "version": "1.0.0",
        "description": "Complete project management system for teachers - Create, manage, and grade student projects",
        "base_url": "/api/teacher/projects/",
        "authentication": "Firebase ID Token (Teacher role required)",
        "overview": {
            "purpose": "Enable teachers to create projects, manage submissions, and provide grading/feedback",
            "key_features": [
                "Create projects with various submission types",
                "Automatically assign projects to enrolled students",
                "Grade submissions with detailed feedback",
                "Track grading progress and statistics",
                "Comprehensive dashboard for project management"
            ],
            "submission_types": [
                "link - Students submit URLs (GitHub repos, live websites)",
                "image - Image uploads (designs, screenshots)",
                "video - Video uploads (presentations, demos)",
                "audio - Audio uploads (podcasts, voice notes)",
                "file - General file uploads (documents, code)",
                "note - Text-based submissions (essays, reflections)",
                "code - Code submissions (programming assignments)",
                "presentation - Presentation files (PowerPoint, PDF)"
            ]
        },
        "endpoints": {
            "project_management": {
                "base_url": "/api/teacher/projects/",
                "description": "CRUD operations for project management",
                "methods": {
                    "GET": {
                        "purpose": "List all projects for teacher's courses",
                        "url": "/api/teacher/projects/",
                        "query_parameters": {
                            "course_id": "uuid (optional) - Filter by specific course",
                            "status": "string (optional) - Filter by project status",
                            "search": "string (optional) - Search by title, instructions, or course name"
                        },
                        "response_structure": {
                            "projects": "Array of Project objects with statistics",
                            "summary": "Overall project statistics and grading progress"
                        },
                        "use_cases": [
                            "Display teacher's project dashboard",
                            "Filter projects by course or search terms",
                            "View project statistics and progress"
                        ]
                    },
                    "POST": {
                        "purpose": "Create a new project assignment",
                        "url": "/api/teacher/projects/",
                        "required_fields": ["course", "title", "instructions", "submission_type", "points"],
                        "optional_fields": ["allowed_file_types", "due_at"],
                        "automation": "Automatically creates submissions for all enrolled students",
                        "validation": "Validates course ownership and positive points",
                        "response": "Created project with statistics"
                    },
                    "PUT": {
                        "purpose": "Update existing project",
                        "url": "/api/teacher/projects/{project_id}/",
                        "fields": "All project fields (partial updates supported)",
                        "ownership_check": "Only project owner (teacher) can update",
                        "response": "Updated project data"
                    },
                    "DELETE": {
                        "purpose": "Delete project",
                        "url": "/api/teacher/projects/{project_id}/",
                        "constraints": "Cannot delete if project has submissions",
                        "response": "Success message with project title"
                    }
                }
            },
            "project_grading": {
                "base_url": "/api/teacher/projects/{project_id}/grading/",
                "description": "Project submission grading and management",
                "methods": {
                    "GET": {
                        "purpose": "View all submissions for a specific project",
                        "url": "/api/teacher/projects/{project_id}/grading/",
                        "query_parameters": {
                            "status": "string (optional) - ASSIGNED|SUBMITTED|RETURNED|GRADED",
                            "search": "string (optional) - Search by student name or email"
                        },
                        "response_structure": {
                            "project": "Project details and metadata",
                            "submissions": "Array of ProjectSubmission objects",
                            "grading_stats": "Statistics for grading progress and scores"
                        },
                        "use_cases": [
                            "Grade all submissions for a project",
                            "Filter submissions by status",
                            "Search for specific student submissions"
                        ]
                    },
                    "PUT": {
                        "purpose": "Grade individual project submission",
                        "url": "/api/teacher/projects/submissions/{submission_id}/",
                        "required_fields": ["status"],
                        "optional_fields": ["points_earned", "feedback"],
                        "status_workflow": "ASSIGNED → SUBMITTED → RETURNED → GRADED",
                        "validation": "GRADED status requires points_earned",
                        "response": "Updated submission with grading data"
                    }
                }
            },
            "submission_detail": {
                "base_url": "/api/teacher/projects/submissions/{submission_id}/",
                "description": "Detailed view and feedback for individual submissions",
                "methods": {
                    "GET": {
                        "purpose": "View detailed submission information",
                        "url": "/api/teacher/projects/submissions/{submission_id}/",
                        "response": "Complete submission and project data"
                    },
                    "POST": {
                        "purpose": "Provide feedback on submission",
                        "url": "/api/teacher/projects/submissions/{submission_id}/",
                        "required_fields": ["status", "feedback"],
                        "status_options": "RETURNED|GRADED",
                        "response": "Updated submission with feedback"
                    }
                }
            },
            "project_dashboard": {
                "base_url": "/api/teacher/projects/dashboard/",
                "description": "Comprehensive project dashboard",
                "methods": {
                    "GET": {
                        "purpose": "Get complete project management overview",
                        "url": "/api/teacher/projects/dashboard/",
                        "response_structure": {
                            "overview": "High-level statistics and counts",
                            "recent_projects": "Latest 5 projects created",
                            "pending_grading": "Submissions waiting for teacher review",
                            "recent_submissions": "Latest 10 submissions across all projects",
                            "course_projects": "Project statistics grouped by course"
                        },
                        "use_cases": [
                            "Teacher dashboard homepage",
                            "Quick overview of project status",
                            "Identify pending grading work",
                            "Monitor project activity across courses"
                        ]
                    }
                }
            }
        },
        "data_models": {
            "Project": {
                "id": "integer - Unique project identifier",
                "course": "integer - Associated course ID",
                "title": "string - Project title",
                "instructions": "string - Detailed project instructions",
                "submission_type": "string - Type of submission expected",
                "allowed_file_types": "array - Permitted file extensions",
                "points": "integer - Maximum points for project",
                "due_at": "datetime - Project due date (optional)",
                "created_at": "datetime - Project creation timestamp",
                "submission_count": "integer - Total submissions (computed)",
                "graded_count": "integer - Graded submissions (computed)",
                "pending_count": "integer - Pending submissions (computed)",
                "requires_file_upload": "boolean - File upload required (computed)",
                "requires_text_input": "boolean - Text input required (computed)",
                "requires_url_input": "boolean - URL input required (computed)"
            },
            "ProjectSubmission": {
                "id": "integer - Unique submission identifier",
                "project": "integer - Associated project ID",
                "student": "integer - Student user ID",
                "status": "string - Submission status",
                "content": "string - Text content (optional)",
                "file_url": "string - Cloud storage URL (optional)",
                "reflection": "string - Student reflection (optional)",
                "submitted_at": "datetime - Submission timestamp (optional)",
                "graded_at": "datetime - Grading timestamp (optional)",
                "grader": "UUID - Teacher who graded (optional)",
                "points_earned": "decimal - Points awarded (optional)",
                "feedback": "string - Teacher feedback (optional)",
                "feedback_response": "string - Student response to feedback (optional)",
                "feedback_checked": "boolean - Student has seen feedback",
                "feedback_checked_at": "datetime - Last feedback check (optional)",
                "created_at": "datetime - Submission creation timestamp",
                "updated_at": "datetime - Last update timestamp"
            }
        },
        "status_workflow": {
            "project_lifecycle": [
                "1. Teacher creates project",
                "2. System auto-creates submissions for enrolled students",
                "3. Students submit work (status: ASSIGNED → SUBMITTED)",
                "4. Teacher grades and provides feedback (status: SUBMITTED → RETURNED/GRADED)",
                "5. Students can respond to feedback (optional)"
            ],
            "submission_statuses": {
                "ASSIGNED": "Project assigned to student, not yet submitted",
                "SUBMITTED": "Student has submitted work, awaiting teacher review",
                "RETURNED": "Teacher has provided feedback, student can resubmit",
                "GRADED": "Final grading complete, project closed"
            }
        },
        "example_requests": {
            "create_project": {
                "url": "POST /api/teacher/projects/",
                "body": {
                    "course": "123e4567-e89b-12d3-a456-426614174000",
                    "title": "Build a Calculator App",
                    "instructions": "Create a calculator with basic operations (+, -, *, /) using HTML, CSS, and JavaScript. Include a clean UI and error handling.",
                    "submission_type": "code",
                    "allowed_file_types": ["html", "css", "js"],
                    "points": 100,
                    "due_at": "2025-10-15T23:59:59Z"
                }
            },
            "grade_submission": {
                "url": "PUT /api/teacher/projects/submissions/456e7890-e89b-12d3-a456-426614174000/",
                "body": {
                    "status": "GRADED",
                    "points_earned": 85,
                    "feedback": "Great work! The calculator functions correctly and has a clean design. Consider adding keyboard support for better UX. -5 points for missing error handling on division by zero."
                }
            },
            "provide_feedback": {
                "url": "POST /api/teacher/projects/submissions/456e7890-e89b-12d3-a456-426614174000/",
                "body": {
                    "status": "RETURNED",
                    "feedback": "Good start! Please add input validation and improve the styling. Resubmit when ready."
                }
            }
        },
        "frontend_integration": {
            "project_creation_form": {
                "fields": ["course", "title", "instructions", "submission_type", "points", "due_at"],
                "validation": "Client-side validation for required fields and positive points",
                "file_type_handling": "Show/hide file type input based on submission_type"
            },
            "grading_interface": {
                "submission_display": "Show student work based on submission_type",
                "grading_form": "Points input, feedback textarea, status dropdown",
                "bulk_actions": "Select multiple submissions for batch operations"
            },
            "dashboard_widgets": {
                "overview_cards": "Total projects, submissions, grading progress",
                "recent_activity": "Latest submissions and projects",
                "pending_work": "Submissions awaiting teacher review",
                "course_breakdown": "Project statistics per course"
            }
        },
        "error_handling": {
            "400": "Bad Request - Invalid data or missing required fields",
            "401": "Unauthorized - Invalid or missing Firebase token",
            "403": "Forbidden - User is not a teacher or doesn't own the resource",
            "404": "Not Found - Project or submission not found",
            "500": "Internal Server Error - Server error during processing"
        },
        "best_practices": {
            "project_creation": [
                "Provide clear, detailed instructions",
                "Set appropriate due dates",
                "Choose correct submission type for the assignment",
                "Specify allowed file types for file uploads"
            ],
            "grading": [
                "Provide constructive feedback",
                "Use consistent grading criteria",
                "Grade submissions promptly",
                "Use RETURNED status for revisions, GRADED for final submissions"
            ],
            "dashboard_usage": [
                "Check dashboard regularly for pending work",
                "Use filters to focus on specific courses or statuses",
                "Monitor overdue submissions",
                "Track grading progress across all projects"
            ]
        }
    }
    
    return JsonResponse(contract, json_dumps_params={'indent': 2})


@require_http_methods(["GET"])
def teacher_assignment_contract(request):
    """
    Teacher Assignment Management API Contract
    Returns detailed API contract for teacher assignment management
    """
    
    contract = {
        "title": "Teacher Assignment Management API Contract",
        "version": "1.0.0",
        "description": "Complete assignment management system for teachers",
        "base_url": "https://your-domain.com/api/teacher/assignments",
        "authentication": {
            "type": "Firebase ID Token",
            "header": "Authorization: Bearer <firebase_id_token>",
            "description": "Firebase authentication token obtained from Firebase Auth",
            "required_role": "teacher"
        },
        "endpoints": {
            "assignment_management": {
                "base_url": "/api/teacher/assignments/",
                "description": "Complete assignment management system for teachers",
                "authentication": "Required (Teacher role)",
                "methods": {
                    "GET": {
                        "url": "/api/teacher/assignments/",
                        "description": "List all assignments for teacher's courses",
                        "query_parameters": {
                            "course_id": "uuid (optional) - Filter by course",
                            "lesson_id": "uuid (optional) - Filter by lesson",
                            "assignment_type": "string (optional) - Filter by type (homework|quiz|exam|project)",
                            "search": "string (optional) - Search by title or description"
                        },
                        "response": {
                            "assignments": [
                                {
                                    "id": "uuid",
                                    "lesson": "uuid",
                                    "lesson_title": "string",
                                    "course_title": "string",
                                    "title": "string",
                                    "description": "string",
                                    "assignment_type": "homework|quiz|exam|project",
                                    "due_date": "datetime (optional)",
                                    "passing_score": "integer",
                                    "max_attempts": "integer",
                                    "show_correct_answers": "boolean",
                                    "randomize_questions": "boolean",
                                    "created_at": "datetime",
                                    "question_count": "integer",
                                    "submission_count": "integer"
                                }
                            ],
                            "total_count": "integer"
                        }
                    },
                    "GET_DETAIL": {
                        "url": "/api/teacher/assignments/{assignment_id}/",
                        "description": "Get detailed assignment information with questions",
                        "response": {
                            "assignment": {
                                "id": "uuid",
                                "lesson": "uuid",
                                "lesson_title": "string",
                                "course_title": "string",
                                "title": "string",
                                "description": "string",
                                "assignment_type": "homework|quiz|exam|project",
                                "due_date": "datetime (optional)",
                                "passing_score": "integer",
                                "max_attempts": "integer",
                                "show_correct_answers": "boolean",
                                "randomize_questions": "boolean",
                                "created_at": "datetime",
                                "questions": [
                                    {
                                        "id": "uuid",
                                        "question_text": "string",
                                        "type": "multiple_choice|true_false|fill_blank|short_answer|essay|flashcard",
                                        "content": "object - Question-specific content",
                                        "points": "integer",
                                        "order": "integer",
                                        "explanation": "string (optional)"
                                    }
                                ]
                            }
                        }
                    },
                    "POST": {
                        "url": "/api/teacher/assignments/",
                        "description": "Create a new assignment",
                        "request_body": {
                            "lesson": "uuid (required) - Lesson ID",
                            "title": "string (required) - Assignment title",
                            "description": "string (optional) - Assignment description",
                            "assignment_type": "string (optional) - homework|quiz|exam|project (default: homework)",
                            "due_date": "datetime (optional) - Due date",
                            "passing_score": "integer (optional) - Minimum score to pass (default: 70)",
                            "max_attempts": "integer (optional) - Max attempts allowed (default: 1)",
                            "show_correct_answers": "boolean (optional) - Show answers after completion (default: false)",
                            "randomize_questions": "boolean (optional) - Randomize question order (default: false)"
                        },
                        "response": {
                            "assignment": "AssignmentDetailSerializer data",
                            "message": "Assignment created successfully"
                        },
                        "features": [
                            "Validates lesson ownership",
                            "Supports all assignment types",
                            "Automatic default values for optional fields"
                        ]
                    },
                    "PUT": {
                        "url": "/api/teacher/assignments/{assignment_id}/",
                        "description": "Update an existing assignment",
                        "request_body": {
                            "title": "string (optional)",
                            "description": "string (optional)",
                            "assignment_type": "string (optional)",
                            "due_date": "datetime (optional)",
                            "passing_score": "integer (optional)",
                            "max_attempts": "integer (optional)",
                            "show_correct_answers": "boolean (optional)",
                            "randomize_questions": "boolean (optional)"
                        },
                        "response": {
                            "assignment": "Updated AssignmentDetailSerializer data",
                            "message": "Assignment updated successfully"
                        }
                    },
                    "DELETE": {
                        "url": "/api/teacher/assignments/{assignment_id}/",
                        "description": "Delete an assignment",
                        "response": {
                            "message": "Assignment deleted successfully"
                        },
                        "constraints": {
                            "submission_check": "Cannot delete if assignment has submissions",
                            "ownership": "Only assignment owner (teacher) can delete"
                        }
                    }
                }
            },
            "assignment_questions": {
                "base_url": "/api/teacher/assignments/{assignment_id}/questions/",
                "description": "Assignment question management system",
                "authentication": "Required (Teacher role)",
                "methods": {
                    "GET": {
                        "url": "/api/teacher/assignments/{assignment_id}/questions/",
                        "description": "List all questions for an assignment",
                        "response": {
                            "questions": [
                                {
                                    "id": "uuid",
                                    "question_text": "string",
                                    "type": "multiple_choice|true_false|fill_blank|short_answer|essay|flashcard",
                                    "content": "object - Question-specific content",
                                    "points": "integer",
                                    "order": "integer",
                                    "explanation": "string (optional)",
                                    "created_at": "datetime"
                                }
                            ]
                        }
                    },
                    "POST": {
                        "url": "/api/teacher/assignments/{assignment_id}/questions/",
                        "description": "Create a new question for an assignment",
                        "request_body": {
                            "question_text": "string (required) - The question text",
                            "type": "string (required) - multiple_choice|true_false|fill_blank|short_answer|essay|flashcard",
                            "content": "object (required) - Question-specific content structure",
                            "points": "integer (required) - Points for this question",
                            "order": "integer (optional) - Question order",
                            "explanation": "string (optional) - Explanation for correct answer"
                        },
                        "content_examples": {
                            "multiple_choice": {
                                "content": {
                                    "options": ["Option A", "Option B", "Option C", "Option D"],
                                    "correct_answer": "Option B"
                                }
                            },
                            "true_false": {
                                "content": {
                                    "correct_answer": True
                                }
                            },
                            "fill_blank": {
                                "content": {
                                    "blanks": ["blank1", "blank2"],
                                    "correct_answers": {
                                        "blank1": "answer1",
                                        "blank2": "answer2"
                                    }
                                }
                            },
                            "short_answer": {
                                "content": {
                                    "correct_answer": "Expected answer",
                                    "accept_variations": True
                                }
                            },
                            "essay": {
                                "content": {
                                    "min_words": 100,
                                    "max_words": 500,
                                    "rubric": "Grading criteria"
                                }
                            },
                            "flashcard": {
                                "content": {
                                    "front": "Question side",
                                    "back": "Answer side"
                                }
                            }
                        },
                        "response": {
                            "question": "AssignmentQuestionSerializer data",
                            "message": "Question created successfully"
                        }
                    },
                    "PUT": {
                        "url": "/api/teacher/assignments/{assignment_id}/questions/{question_id}/",
                        "description": "Update an existing question",
                        "request_body": {
                            "question_text": "string (optional)",
                            "type": "string (optional)",
                            "content": "object (optional)",
                            "points": "integer (optional)",
                            "order": "integer (optional)",
                            "explanation": "string (optional)"
                        },
                        "response": {
                            "question": "Updated AssignmentQuestionSerializer data",
                            "message": "Question updated successfully"
                        }
                    },
                    "DELETE": {
                        "url": "/api/teacher/assignments/{assignment_id}/questions/{question_id}/",
                        "description": "Delete a question",
                        "response": {
                            "message": "Question deleted successfully"
                        },
                        "constraints": {
                            "ownership": "Only assignment owner (teacher) can delete questions"
                        }
                    }
                }
            }
        }
    }
    
    return JsonResponse(contract, json_dumps_params={'indent': 2})


@require_http_methods(["GET"])
def class_events_contract(request):
    """
    Class Events Management API Contract
    Returns detailed API contract for class event management
    """
    
    contract = {
        "title": "Class Events Management API Contract",
        "version": "1.0.0",
        "description": "Complete class event management system for teachers - Schedule lessons, projects, breaks, and meetings",
        "base_url": "/api/courses/classes/{class_id}/events/",
        "authentication": {
            "type": "Firebase ID Token",
            "header": "Authorization: Bearer <firebase_id_token>",
            "description": "Firebase authentication token obtained from Firebase Auth",
            "required_role": "teacher"
        },
        "overview": {
            "purpose": "Enable teachers to create and manage class schedules with various event types",
            "key_features": [
                "Schedule lessons from course curriculum",
                "Schedule project work sessions with platforms",
                "Create meeting and break events",
                "Get all available resources in one API call",
                "Comprehensive event management"
            ],
            "event_types": [
                "lesson - Scheduled lesson from course curriculum",
                "project - Scheduled project work session",
                "meeting - General meeting or discussion",
                "break - Break time between activities"
            ]
        },
        "endpoints": {
            "class_events": {
                "base_url": "/api/courses/classes/{class_id}/events/",
                "description": "Complete class event management system",
                "authentication": "Required (Teacher role)",
                "methods": {
                    "GET": {
                        "url": "/api/courses/classes/{class_id}/events/",
                        "description": "Get all events for a class with available resources",
                        "path_parameters": {
                            "class_id": "uuid (required) - Class identifier"
                        },
                        "response_structure": {
                            "class_info": {
                                "class_id": "uuid",
                                "class_name": "string",
                                "course_id": "uuid",
                                "course_name": "string"
                            },
                            "events": "Array of ClassEvent objects",
                            "available_lessons": "Array of Lesson objects for the course",
                            "available_projects": "Array of Project objects for the course",
                            "available_platforms": "Array of active ProjectPlatform objects"
                        },
                        "use_cases": [
                            "Display class schedule/calendar",
                            "Show available resources for creating new events",
                            "Get comprehensive class event data in one API call"
                        ]
                    },
                    "POST": {
                        "url": "/api/courses/classes/{class_id}/events/",
                        "description": "Create a new class event",
                        "path_parameters": {
                            "class_id": "uuid (required) - Class identifier"
                        },
                        "request_body": {
                            "title": "string (required)",
                            "description": "string (optional)",
                            "event_type": "lesson|project|meeting|break (required)",
                            "start_time": "datetime (required)",
                            "end_time": "datetime (required)",
                            "lesson": "integer (required for lesson events)",
                            "project": "integer (required for project events)",
                            "project_platform": "uuid (required for project events)",
                            "lesson_type": "text|video|audio|live (optional)",
                            "meeting_platform": "string (optional for live lessons)",
                            "meeting_link": "string (optional for live lessons)",
                            "meeting_id": "string (optional for live lessons)",
                            "meeting_password": "string (optional for live lessons)"
                        },
                        "response": {
                            "event": "ClassEventDetailSerializer data",
                            "message": "Event created successfully"
                        },
                        "validation_rules": {
                            "lesson_events": "Must specify lesson field",
                            "project_events": "Must specify project and project_platform fields",
                            "time_validation": "end_time must be after start_time",
                            "project_course_match": "Project must belong to the same course as the class"
                        }
                    }
                }
            }
        },
        "data_structures": {
            "ClassEvent": {
                "id": "uuid",
                "title": "string",
                "description": "string",
                "event_type": "lesson|project|meeting|break",
                "lesson_type": "text|video|audio|live (for lesson events)",
                "start_time": "datetime",
                "end_time": "datetime",
                "duration_minutes": "integer",
                "lesson_title": "string (for lesson events)",
                "project_title": "string (for project events)",
                "project_platform_name": "string (for project events)",
                "meeting_platform": "string (for live lessons)",
                "meeting_link": "string (for live lessons)",
                "meeting_id": "string (for live lessons)",
                "meeting_password": "string (for live lessons)",
                "created_at": "datetime",
                "updated_at": "datetime"
            },
            "Lesson": {
                "id": "integer",
                "title": "string",
                "description": "string",
                "type": "text|video|audio|live",
                "duration": "integer",
                "order": "integer",
                "status": "string",
                "created_at": "datetime"
            },
            "Project": {
                "id": "integer",
                "title": "string",
                "instructions": "string",
                "submission_type": "link|image|video|audio|file|note|code|presentation",
                "points": "integer",
                "due_at": "datetime (optional)",
                "created_at": "datetime"
            },
            "ProjectPlatform": {
                "id": "uuid",
                "name": "string",
                "display_name": "string",
                "description": "string",
                "platform_type": "string",
                "base_url": "string",
                "icon": "string",
                "color": "string",
                "is_active": "boolean",
                "is_featured": "boolean",
                "is_free": "boolean",
                "min_age": "integer (optional)",
                "max_age": "integer (optional)",
                "skill_levels": "array of strings",
                "capabilities": "array of strings"
            }
        },
        "platforms": {
            "description": "Project platforms available for project events",
            "categories": [
                "Visual Programming (Scratch, ScratchJr, Blockly)",
                "Online IDE (Replit, CodePen, JSFiddle)",
                "Design Tools (Figma, Canva)",
                "Data Science (Jupyter Notebook, Google Colab)",
                "Game Development (Unity, Godot)",
                "Electronics (Arduino IDE, Arduino Create, Tinkercad, Wokwi, Virtual Breadboard)"
            ],
            "features": [
                "Age-appropriate recommendations",
                "Skill level filtering",
                "Collaboration support",
                "File upload capabilities",
                "Live preview options"
            ]
        },
        "examples": {
            "get_class_events": {
                "url": "/api/courses/classes/f0e4fe8b-4c52-4333-8b85-11af7ed1e750/events/",
                "method": "GET",
                "headers": {
                    "Authorization": "Bearer <firebase_id_token>"
                },
                "response": {
                    "class_id": "f0e4fe8b-4c52-4333-8b85-11af7ed1e750",
                    "class_name": "English afternoon class",
                    "course_id": "37ffa9a4-bf4f-4117-9cdd-be3d5c428f35",
                    "course_name": "English",
                    "events": [
                        {
                            "id": "uuid",
                            "title": "Introduction to Programming",
                            "event_type": "lesson",
                            "start_time": "2024-01-15T10:00:00Z",
                            "end_time": "2024-01-15T11:00:00Z",
                            "lesson_title": "Introduction to Programming"
                        }
                    ],
                    "available_lessons": [
                        {
                            "id": 1,
                            "title": "Introduction to Programming",
                            "type": "text",
                            "duration": 60
                        }
                    ],
                    "available_projects": [
                        {
                            "id": 11,
                            "title": "Build an action script",
                            "submission_type": "code"
                        }
                    ],
                    "available_platforms": [
                        {
                            "id": "uuid",
                            "name": "scratch",
                            "display_name": "Scratch Programming Platform",
                            "platform_type": "Visual Programming",
                            "is_active": True
                        }
                    ]
                }
            },
            "create_lesson_event": {
                "url": "/api/courses/classes/f0e4fe8b-4c52-4333-8b85-11af7ed1e750/events/",
                "method": "POST",
                "headers": {
                    "Authorization": "Bearer <firebase_id_token>",
                    "Content-Type": "application/json"
                },
                "body": {
                    "title": "Introduction to Programming",
                    "description": "First lesson of the course",
                    "event_type": "lesson",
                    "start_time": "2024-01-15T10:00:00Z",
                    "end_time": "2024-01-15T11:00:00Z",
                    "lesson": 1,
                    "lesson_type": "text"
                }
            },
            "create_project_event": {
                "url": "/api/courses/classes/f0e4fe8b-4c52-4333-8b85-11af7ed1e750/events/",
                "method": "POST",
                "headers": {
                    "Authorization": "Bearer <firebase_id_token>",
                    "Content-Type": "application/json"
                },
                "body": {
                    "title": "Scratch Project Session",
                    "description": "Work on Scratch programming project",
                    "event_type": "project",
                    "start_time": "2024-01-15T14:00:00Z",
                    "end_time": "2024-01-15T16:00:00Z",
                    "project": 11,
                    "project_platform": "uuid-of-scratch-platform"
                }
            }
        }
    }
    
    return JsonResponse(contract, json_dumps_params={'indent': 2})
