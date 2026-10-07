"""Structured output for quiz generation (MC + true/false)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class QuizQuestionOut(BaseModel):
    question_text: str = Field(description="The question text shown to the student")
    type: Literal["multiple_choice", "true_false"] = Field(
        description="Question type: multiple_choice or true_false"
    )
    points: int = Field(default=1, ge=1, description="Points awarded for this question")
    content: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Question-specific content. For multiple_choice: "
            '{"options": ["A","B","C","D"], "correct_answer": "exact option text"}. '
            'For true_false: {"correct_answer": "true" or "false"}.'
        ),
    )
    explanation: str = Field(
        default="",
        description="Short explanation shown after answering",
    )
    # Tolerant of models that put options/correct_answer at the top level
    options: Optional[list[Any]] = Field(
        default=None,
        description="Optional top-level options (merged into content for multiple_choice)",
    )
    correct_answer: Optional[Any] = Field(
        default=None,
        description="Optional top-level correct_answer (merged into content)",
    )

    @field_validator("question_text", "explanation")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return (value or "").strip()


class QuizGenerateOut(BaseModel):
    title: str = Field(description="Quiz title")
    description: str = Field(default="", description="Quiz description")
    questions: list[QuizQuestionOut] = Field(
        description="List of quiz questions (multiple_choice and true_false only)"
    )

    @field_validator("title", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return (value or "").strip()
