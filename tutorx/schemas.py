"""
TutorX response schemas for structured AI output.

Single place for:
- Student Ask: generate_questions (quiz-style), harder_questions (assignment-style).
- Block action: generate_questions (simple question/type/difficulty array).
- Lesson chat: tool declarations for intent (explain_better, generate_questions, draw_explainer_image)
  and response schemas (qanda reuses student generate; draw_explainer_image has its own).

Frontend: response_type "text" | "qanda" | "explainer_image" maps to these where applicable.
"""
from typing import Any, Dict, List


def get_student_generate_questions_schema() -> Dict[str, Any]:
    """
    Schema for Student Ask "Generate questions" / "Test my knowledge" (first call).
    Quiz-style: multiple_choice and true_false with options and correct_answer.
    Response includes a closing message to prompt for harder questions.
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
                            "description": "The question text shown to the student",
                        },
                        "type": {
                            "type": "string",
                            "enum": ["multiple_choice", "true_false"],
                            "description": "Question type: multiple_choice or true_false",
                        },
                        "difficulty": {
                            "type": "string",
                            "enum": ["easy", "medium"],
                            "description": "Difficulty level for this question",
                        },
                        "content": {
                            "type": "object",
                            "description": "For multiple_choice: {\"options\": [\"A\", \"B\", \"C\", \"D\"], \"correct_answer\": \"A\" (exact option text)}. For true_false: {\"correct_answer\": \"true\" or \"false\"}.",
                            "properties": {
                                "options": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Required for multiple_choice. List of choice texts.",
                                },
                                "correct_answer": {
                                    "type": "string",
                                    "description": "The correct answer: for MC the exact option text; for true_false either \"true\" or \"false\".",
                                },
                            },
                            "required": ["correct_answer"],
                        },
                        "explanation": {
                            "type": "string",
                            "description": "Optional explanation shown after the student reveals the answer",
                        },
                    },
                    "required": ["question_text", "type", "difficulty", "content"],
                },
                "description": "List of quiz-style questions (multiple choice and true/false)",
            },
            "message": {
                "type": "string",
                "description": "A short, friendly closing message to the student (e.g. offering more or harder questions, or asking if they need anything else). One sentence.",
            },
        },
        "required": ["questions", "message"],
    }


def get_student_harder_questions_schema() -> Dict[str, Any]:
    """
    Schema for Student Ask "harder questions" follow-up.
    Assignment-style: short_answer, essay, fill_blank — open-ended, harder.
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
                            "description": "The question text shown to the student",
                        },
                        "type": {
                            "type": "string",
                            "enum": ["short_answer", "essay", "fill_blank"],
                            "description": "Question type: short_answer, essay, or fill_blank",
                        },
                        "difficulty": {
                            "type": "string",
                            "enum": ["medium", "hard"],
                            "description": "Difficulty level for this question",
                        },
                        "content": {
                            "type": "object",
                            "description": "For short_answer: {\"correct_answer\": \"string\", \"accept_variations\": true/false}. For essay: {\"instructions\": \"optional instructions for the student\"}. For fill_blank: {\"blanks\": [\"blank1\", \"blank2\"], \"correct_answers\": {\"0\": \"answer1\", \"1\": \"answer2\"}}.",
                            "properties": {
                                "correct_answer": {
                                    "type": "string",
                                    "description": "Model answer / correct answer shown when student clicks Show answer. Required for short_answer and essay.",
                                },
                                "accept_variations": {
                                    "type": "boolean",
                                    "description": "For short_answer: whether to accept equivalent phrasings",
                                },
                                "instructions": {
                                    "type": "string",
                                    "description": "Optional instructions for essay questions",
                                },
                                "blanks": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "For fill_blank: list of placeholder strings (e.g. [\"_____\", \"_____\"])",
                                },
                                "correct_answers": {
                                    "type": "object",
                                    "description": "For fill_blank: object mapping index as string to correct answer, e.g. {\"0\": \"ans1\", \"1\": \"ans2\"}",
                                },
                            },
                        },
                        "explanation": {
                            "type": "string",
                            "description": "Optional explanation or model answer details shown after the student reveals the answer",
                        },
                    },
                    "required": ["question_text", "type", "difficulty", "content"],
                },
                "description": "List of harder, open-ended questions",
            },
        },
        "required": ["questions"],
    }


def get_block_generate_questions_schema() -> Dict[str, Any]:
    """
    Schema for block-action "Generate questions" (block popup menu).
    Simple array of { question, type, difficulty }. Use this from block actions for consistency.
    """
    return {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "type": {"type": "string"},
                "difficulty": {"type": "string"},
            },
            "required": ["question", "type", "difficulty"],
        },
    }


def get_lesson_chat_tool_declarations() -> List[Dict[str, Any]]:
    """
    Tool/function declarations for lesson chat intent inference (e.g. Gemini function calling).
    Model chooses which tool to call from user message; we dispatch to the right handler.
    """
    return [
        {
            "name": "explain_better",
            "description": "Explain a phrase or concept from the lesson in simpler terms or at a different level (e.g. explain like I'm 5). Use when the student asks for a simpler explanation, rephrasing, or clarification.",
        },
        {
            "name": "generate_questions",
            "description": "Generate quiz or practice questions (and optionally model answers) based on the lesson content. Use when the student asks to generate questions, test their knowledge, or get Q&A.",
        },
        {
            "name": "draw_explainer_image",
            "description": "Generate a description or prompt for an explainer/diagram image that illustrates a concept from the lesson. Use when the student asks for a diagram, visual explanation, or picture to explain something.",
        },
    ]


def get_lesson_chat_tool_schemas_vertex() -> List[Dict[str, Any]]:
    """
    Lesson chat tools in Vertex AI format (name, description, parameters).
    Use with GeminiService.generate_with_tools for AI-based intent inference.
    """
    return [
        {
            "name": "explain_better",
            "description": "Explain a phrase or concept from the lesson in simpler terms or at a different level (e.g. explain like I'm 5). Use when the student asks for a simpler explanation, rephrasing, clarification, or says they don't understand something.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phrase_or_concept": {
                        "type": "string",
                        "description": "The phrase, concept, or part of the lesson the student wants explained more simply.",
                    },
                    "user_message": {
                        "type": "string",
                        "description": "The student's full message for context.",
                    },
                },
                "required": ["user_message"],
            },
        },
        {
            "name": "generate_questions",
            "description": "Generate quiz or practice questions (and optionally model answers) based on the lesson content. Use when the student asks to generate questions, test their knowledge, or get Q&A.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_message": {
                        "type": "string",
                        "description": "The student's request (e.g. 'generate questions', 'test me', 'give me Q&A').",
                    },
                },
                "required": ["user_message"],
            },
        },
        {
            "name": "draw_explainer_image",
            "description": "Generate a description or prompt for an explainer/diagram image that illustrates a concept from the lesson. Use when the student asks for a diagram, visual explanation, or picture to explain something.",
            "parameters": {
                "type": "object",
                "properties": {
                    "concept": {
                        "type": "string",
                        "description": "The concept or topic to illustrate.",
                    },
                    "user_message": {
                        "type": "string",
                        "description": "The student's full message.",
                    },
                },
                "required": ["user_message"],
            },
        },
    ]


def get_draw_explainer_image_schema() -> Dict[str, Any]:
    """
    Response schema for lesson-chat draw_explainer_image.
    Returns structured data for downstream image generation (e.g. image_description for alt text, image_prompt for an image API).
    response_type: "explainer_image".
    """
    return {
        "type": "object",
        "properties": {
            "image_description": {
                "type": "string",
                "description": "Short description of the image for accessibility / alt text.",
            },
            "image_prompt": {
                "type": "string",
                "description": "Detailed prompt for generating the explainer image (e.g. for an image generation API).",
            },
        },
        "required": ["image_description", "image_prompt"],
    }
