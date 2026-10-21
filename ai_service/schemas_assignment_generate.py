"""Structured output for assignment generation (essay / fill_blank)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class AssignmentQuestionOut(BaseModel):
    question_text: str = Field(description="The question text shown to the student")
    type: Literal["essay", "fill_blank"] = Field(
        description="Question type: essay or fill_blank. A brief written response is an essay."
    )
    points: int = Field(default=10, ge=1, description="Points awarded for this question")
    content: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Question-specific content. "
            'For fill_blank: {"blanks": ["..."], "correct_answers": {"blank1": "..."}}. '
            'For essay: {"correct_answer": "full model answer", "instructions": "optional student instructions"}. '
            "Never include a rubric field. "
            "Do not use a short_answer type."
        ),
    )
    explanation: str = Field(
        description=(
            "Required for every question. Explain why the correct answer is right "
            "and what a complete response should include."
        ),
    )

    @field_validator("question_text", "explanation")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return (value or "").strip()

    @model_validator(mode="after")
    def require_answer_and_explanation(self) -> "AssignmentQuestionOut":
        if not (self.explanation or "").strip():
            raise ValueError("explanation is required for every question")
        content = self.content if isinstance(self.content, dict) else {}
        if self.type == "fill_blank":
            answers = content.get("correct_answers")
            has_answers = (
                isinstance(answers, dict) and any(str(v).strip() for v in answers.values())
            ) or (isinstance(answers, list) and any(str(v).strip() for v in answers))
            if not has_answers:
                raise ValueError(
                    "fill_blank requires content.correct_answers with the expected answers"
                )
        else:
            answer = str(content.get("correct_answer") or "").strip()
            if not answer:
                raise ValueError(
                    f"{self.type} requires content.correct_answer"
                )
        return self


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
