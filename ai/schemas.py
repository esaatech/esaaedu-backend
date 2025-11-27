"""
Output schemas for structured AI responses
Separated from logic for reusability and maintainability
"""
from typing import Dict, Any


def get_course_generation_schema() -> Dict[str, Any]:
    """
    Schema for course generation structured output
    
    Returns:
        JSON Schema dict for course generation
    """
    return {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Course title"
            },
            "description": {
                "type": "string",
                "description": "Short course description"
            },
            "long_description": {
                "type": "string",
                "description": "Detailed course description"
            },
            "category": {
                "type": "string",
                "description": "Course category name"
            }
        },
        "required": ["title", "description"]
    }


def get_course_management_function_schema() -> list:
    """
    Schema for function calling in course management context
    Returns functions for managing existing courses (no generate_course)
    
    Returns:
        List of function declaration schemas for course management
    """
    all_functions = get_function_calling_schema()
    # Filter out generate_course, keep only management functions
    return [func for func in all_functions if func["name"] != "generate_course"]


def get_function_calling_schema() -> list:
    """
    Schema for function calling - defines what the AI can call
    This is used by Vertex AI's function calling feature
    
    Returns:
        List of function declaration schemas
    """
    return [
        {
            "name": "generate_course",
            "description": "Generate a structured course outline immediately when the user requests to create, generate, or make a course. Call this function as soon as the user mentions a course topic or subject, even if minimal details are provided. Use the available information to create a comprehensive course.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_request": {
                        "type": "string",
                        "description": "The user's original request for course generation, including any specific requirements or topics they mentioned"
                    },
                    "title": {
                        "type": "string",
                        "description": "Desired course title (if user specified one)"
                    },
                    "topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific topics or subjects the user wants in the course (if mentioned)"
                    }
                },
                "required": ["user_request"]
            }
        },
        {
            "name": "generate_course_introduction",
            "description": "Generate comprehensive course introduction details when the user requests to add or create an introduction for a course. This includes overview, learning objectives, prerequisites, duration, sessions per week, total projects, and value propositions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_request": {
                        "type": "string",
                        "description": "The user's request for course introduction generation"
                    },
                    "course_title": {
                        "type": "string",
                        "description": "The title of the course for which to generate introduction"
                    },
                    "course_description": {
                        "type": "string",
                        "description": "The description of the course for context"
                    }
                },
                "required": ["user_request", "course_title", "course_description"]
            }
        },
        {
            "name": "generate_lesson",
            "description": "Generate lesson outlines (titles and descriptions) for an entire course when the user requests to create lessons. The AI should use course context from the conversation if available. Generate multiple lessons that follow a scaffolding/cumulative organization based on the course duration (weeks) and sessions per week. If duration_weeks or sessions_per_week are not provided, ask the user for this information. Call this function when the user mentions creating lessons, generating lessons, or wants to create lesson content for a course.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_request": {
                        "type": "string",
                        "description": "The user's request for lesson generation, including any specific requirements"
                    },
                    "course_title": {
                        "type": "string",
                        "description": "The title of the course (optional - use conversation context if available)"
                    },
                    "course_description": {
                        "type": "string",
                        "description": "The description of the course (optional - use conversation context if available)"
                    },
                    "duration_weeks": {
                        "type": "integer",
                        "description": "Number of weeks the course runs (optional - ask user if not provided)"
                    },
                    "sessions_per_week": {
                        "type": "integer",
                        "description": "Number of sessions per week (optional - ask user if not provided)"
                    }
                },
                "required": ["user_request"]
            }
        },
        {
            "name": "generate_assignment",
            "description": "Generate an assignment with questions when the user requests to create an assignment from material content. The material content will be provided in the user's message. Call this function when the user mentions creating an assignment, generating assignment questions, or wants to create assignments from study materials.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_request": {
                        "type": "string",
                        "description": "The user's request for assignment generation, including the material content from which to create the assignment"
                    }
                },
                "required": ["user_request"]
            }
        },
        {
            "name": "generate_quiz",
            "description": "Generate a quiz with questions when the user requests to create a quiz from material content. The material content will be provided in the user's message. Call this function when the user mentions creating a quiz, generating quiz questions, or wants to create quizzes from study materials.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_request": {
                        "type": "string",
                        "description": "The user's request for quiz generation, including the material content from which to create the quiz"
                    }
                },
                "required": ["user_request"]
            }
        }
    ]


def get_course_introduction_schema() -> Dict[str, Any]:
    """
    Schema for course introduction generation structured output
    
    Returns:
        JSON Schema dict for course introduction generation
    """
    return {
        "type": "object",
        "properties": {
            "overview": {
                "type": "string",
                "description": "Detailed course overview (extended description)"
            },
            "learning_objectives": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of detailed learning objectives"
            },
            "prerequisites_text": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of prerequisites as JSON array"
            },
            "duration_weeks": {
                "type": "integer",
                "description": "Course duration in weeks"
            },
            "sessions_per_week": {
                "type": "integer",
                "description": "Number of sessions per week"
            },
            "total_projects": {
                "type": "integer",
                "description": "Number of projects students will create"
            },
            "max_students": {
                "type": "integer",
                "description": "Maximum number of students for the course (optional - will use default if not provided)"
            },
            "value_propositions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Value proposition title/heading"
                        },
                        "description": {
                            "type": "string",
                            "description": "Value proposition description"
                        }
                    },
                    "required": ["title", "description"]
                },
                "description": "List of course benefits and value propositions (icon will be added automatically)"
            }
        },
        "required": ["overview", "learning_objectives", "value_propositions"]
    }


def get_lesson_generation_schema() -> Dict[str, Any]:
    """
    Schema for lesson generation structured output
    Returns an array of lessons for the entire course
    
    Returns:
        JSON Schema dict for lesson generation
    """
    return {
        "type": "object",
        "properties": {
            "lessons": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Lesson title"
                        },
                        "description": {
                            "type": "string",
                            "description": "Lesson description"
                        },
                        "order": {
                            "type": "integer",
                            "description": "Lesson order/sequence number (1-based)"
                        },
                        "type": {
                            "type": "string",
                            "enum": ["live_class", "video_audio", "text_lesson"],
                            "description": "Lesson type (default: live_class if not provided)"
                        },
                        "duration": {
                            "type": "integer",
                            "description": "Lesson duration in minutes (default: 45 if not provided)"
                        }
                    },
                    "required": ["title", "description", "order"]
                },
                "description": "Array of lessons for the course, organized in cumulative/scaffolded order"
            }
        },
        "required": ["lessons"]
    }


def get_assignment_generation_schema() -> Dict[str, Any]:
    """
    Schema for assignment generation structured output
    
    Returns:
        JSON Schema dict for assignment generation
    """
    return {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Assignment title"
            },
            "description": {
                "type": "string",
                "description": "Assignment description"
            },
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question_text": {
                            "type": "string",
                            "description": "The question text"
                        },
                        "type": {
                            "type": "string",
                            "enum": ["essay", "fill_blank", "short_answer"],
                            "description": "Question type: essay, fill_blank, or short_answer"
                        },
                        "points": {
                            "type": "integer",
                            "description": "Points awarded for this question",
                            "minimum": 1
                        },
                        "content": {
                            "type": "object",
                            "description": "Question-specific content. For fill_blank: {\"blanks\": [\"string\"], \"correct_answers\": {\"blank1\": \"answer1\", \"blank2\": \"answer2\"}}. For essay: {\"instructions\": \"string\" (optional instructions for students)} - CRITICAL: DO NOT include 'rubric' field. For essay questions, ALL grading information must be in the explanation field only, never in content.rubric. For short_answer: {\"correct_answer\": \"string\", \"accept_variations\": boolean}.",
                            "properties": {
                                "instructions": {"type": "string"},
                                "blanks": {"type": "array", "items": {"type": "string"}},
                                "correct_answers": {"type": "object"},
                                "correct_answer": {"type": "string"},
                                "accept_variations": {"type": "boolean"}
                            },
                            "additionalProperties": False
                        },
                        "explanation": {
                            "type": "string",
                            "description": "For essay questions: A detailed model answer/correct answer that demonstrates what a complete, high-quality response looks like. This should include specific examples, explanations, and key points that students should cover. If there's no single correct answer, provide comprehensive guidance that helps graders evaluate student responses. For other question types: Explanation shown after answering (optional)."
                        }
                    },
                    "required": ["question_text", "type", "points"]
                },
                "description": "List of assignment questions"
            }
        },
        "required": ["title", "description", "questions"]
    }


def get_assessment_generation_schema() -> Dict[str, Any]:
    """
    Schema for assessment (test/exam) generation structured output
    
    Returns:
        JSON Schema dict for assessment generation
    """
    return {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question_text": {
                            "type": "string",
                            "description": "The question text"
                        },
                        "type": {
                            "type": "string",
                            "enum": ["multiple_choice", "true_false", "fill_blank", "short_answer", "essay"],
                            "description": "Question type: multiple_choice, true_false, fill_blank, short_answer, or essay"
                        },
                        "points": {
                            "type": "integer",
                            "description": "Points awarded for this question",
                            "minimum": 1
                        },
                        "content": {
                            "type": "object",
                            "description": "Question-specific content. For multiple_choice: {\"options\": [\"option1\", \"option2\", ...], \"correct_answer\": \"option1\", \"full_options\": {\"options\": [{\"id\": \"option-0\", \"text\": \"option1\", \"isCorrect\": true, \"explanation\": \"why correct\"}, {\"id\": \"option-1\", \"text\": \"option2\", \"isCorrect\": false, \"explanation\": \"why wrong\"}, ...]}} (full_options is optional but recommended). For true_false: {\"correct_answer\": \"true\" or \"false\", \"full_options\": {\"trueOption\": {\"id\": \"true\", \"text\": \"True\", \"isCorrect\": true, \"explanation\": \"...\"}, \"falseOption\": {\"id\": \"false\", \"text\": \"False\", \"isCorrect\": false, \"explanation\": \"...\"}}} (full_options optional). For fill_blank: {\"blanks\": [\"string\"], \"correct_answers\": {\"0\": \"answer1\", \"1\": \"answer2\"}}. For essay: {\"instructions\": \"string\" (optional), \"correct_answer\": \"string\" (model answer)}. For short_answer: {\"correct_answer\": \"string\", \"accept_variations\": boolean}.",
                            "properties": {
                                "options": {"type": "array", "items": {"type": "string"}},
                                "correct_answer": {"type": "string"},
                                "full_options": {
                                    "type": "object",
                                    "description": "Optional rich options with explanations. For multiple_choice: {\"options\": [{\"id\": \"string\", \"text\": \"string\", \"isCorrect\": boolean, \"explanation\": \"string\"}]}. For true_false: {\"trueOption\": {\"id\": \"true\", \"text\": \"True\", \"isCorrect\": boolean, \"explanation\": \"string\"}, \"falseOption\": {\"id\": \"false\", \"text\": \"False\", \"isCorrect\": boolean, \"explanation\": \"string\"}}.",
                                    "properties": {
                                        "options": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "id": {"type": "string"},
                                                    "text": {"type": "string"},
                                                    "isCorrect": {"type": "boolean"},
                                                    "explanation": {"type": "string"}
                                                },
                                                "required": ["id", "text", "isCorrect"]
                                            }
                                        },
                                        "trueOption": {
                                            "type": "object",
                                            "properties": {
                                                "id": {"type": "string"},
                                                "text": {"type": "string"},
                                                "isCorrect": {"type": "boolean"},
                                                "explanation": {"type": "string"}
                                            },
                                            "required": ["id", "text", "isCorrect"]
                                        },
                                        "falseOption": {
                                            "type": "object",
                                            "properties": {
                                                "id": {"type": "string"},
                                                "text": {"type": "string"},
                                                "isCorrect": {"type": "boolean"},
                                                "explanation": {"type": "string"}
                                            },
                                            "required": ["id", "text", "isCorrect"]
                                        }
                                    }
                                },
                                "blanks": {"type": "array", "items": {"type": "string"}},
                                "correct_answers": {"type": "object"},
                                "instructions": {"type": "string"},
                                "accept_variations": {"type": "boolean"}
                            },
                            "additionalProperties": False
                        },
                        "explanation": {
                            "type": "string",
                            "description": "Explanation shown after answering. For essay questions: A detailed model answer that demonstrates what a complete, high-quality response looks like."
                        }
                    },
                    "required": ["question_text", "type", "points"]
                },
                "description": "List of assessment questions"
            }
        },
        "required": ["questions"]
    }


def get_quiz_generation_schema() -> Dict[str, Any]:
    """
    Schema for quiz generation structured output
    
    Returns:
        JSON Schema dict for quiz generation
    """
    return {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Quiz title"
            },
            "description": {
                "type": "string",
                "description": "Quiz description"
            },
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question_text": {
                            "type": "string",
                            "description": "The question text"
                        },
                        "type": {
                            "type": "string",
                            "enum": ["multiple_choice", "true_false"],
                            "description": "Question type: multiple_choice or true_false"
                        },
                        "points": {
                            "type": "integer",
                            "description": "Points awarded for this question",
                            "minimum": 1
                        },
                        "content": {
                            "type": "object",
                            "description": "Question-specific content. For multiple_choice: {\"options\": [\"string\"], \"correct_answer\": \"string\" (index or option text)}. For true_false: {\"correct_answer\": \"true\" or \"false\"}."
                        },
                        "explanation": {
                            "type": "string",
                            "description": "Explanation shown after answering (optional)"
                        }
                    },
                    "required": ["question_text", "type", "points", "content"]
                },
                "description": "List of quiz questions"
            }
        },
        "required": ["title", "description", "questions"]
    }


def get_course_detail_schema() -> Dict[str, Any]:
    """
    Schema for course detail generation structured output
    Returns basic course information: title, descriptions, category, and difficulty level
    
    Returns:
        JSON Schema dict for course detail generation
    """
    return {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Course title"
            },
            "short_description": {
                "type": "string",
                "description": "Short course description (brief overview, 1-2 sentences)"
            },
            "detailed_description": {
                "type": "string",
                "description": "Detailed course description (comprehensive overview, multiple paragraphs)"
            },
            "category": {
                "type": "string",
                "description": "Course category (e.g., 'Programming', 'Mathematics', 'Science', 'Arts', etc.)"
            },
            "difficulty_level": {
                "type": "string",
                "enum": ["beginner", "intermediate", "advanced"],
                "description": "Course difficulty level: beginner, intermediate, or advanced"
            }
        },
        "required": ["title", "short_description", "detailed_description", "category", "difficulty_level"]
    }

