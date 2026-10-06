"""Structured output for TutorX assignment question grading."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class TutorXQuestionGradeOut(BaseModel):
    """One AI-graded TutorX assignment question (essay / fill_blank / open short_answer)."""

    points_earned: float = Field(
        description=(
            "Points awarded from 0 to points_possible (decimals allowed for partial credit). "
            "Use 0 if the question cannot be graded."
        )
    )
    feedback: str = Field(
        description=(
            "Constructive feedback written directly to the student in second person "
            "(you / your). No prefixes like Reasoning: or Feedback:."
        )
    )
    correct_answer: str = Field(
        description=(
            "Correct or model answer for the student. For open-ended work, frame around "
            "the student's topic when appropriate while showing expected completeness."
        )
    )
    confidence: float = Field(
        default=0.8,
        description="Confidence in the grade from 0.0 to 1.0",
    )

    @field_validator("feedback", "correct_answer")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return (value or "").strip()
