"""Structured output for assignment generation (essay / fill_blank / short_answer)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class AssignmentQuestionOut(BaseModel):
    question_text: str = Field(description="The question text shown to the student")
    type: Literal["essay", "fill_blank", "short_answer"] = Field(
        description="Question type: essay, fill_blank, or short_answer"
    )
    points: int = Field(default=10, ge=1, description="Points awarded for this question")
    content: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Question-specific content. "
            'For fill_blank: {"blanks": ["..."], "correct_answers": {"blank1": "..."}}. '
            'For essay: {"instructions": "optional student instructions"} — '
            "never include a rubric field; put model answers in explanation. "
            'For short_answer: {"correct_answer": "...", "accept_variations": true}.'
        ),
    )
    explanation: str = Field(
        default="",
        description=(
            "For essay: detailed model answer / grading guide. "
            "For other types: optional explanation."
        ),
    )

    @field_validator("question_text", "explanation")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return (value or "").strip()


class AssignmentGenerateOut(BaseModel):
    title: str = Field(description="Assignment title")
    description: str = Field(default="", description="Assignment description")
    questions: list[AssignmentQuestionOut] = Field(
        description="List of assignment questions"
    )

    @field_validator("title", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return (value or "").strip()
