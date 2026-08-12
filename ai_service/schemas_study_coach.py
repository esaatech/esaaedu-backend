"""Structured output for Study Coach quiz-card deck generation."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, field_validator, model_validator


QuestionType = Literal["multiple_choice", "true_false", "short_answer"]
CardDifficulty = Literal["easy", "hard"]
DifficultyMode = Literal["easy", "hard", "auto"]


class StudyCardOut(BaseModel):
    question_type: QuestionType
    # Keep schema simple for model-serving (avoid min_length/max constraints).
    prompt: str
    options: Optional[list[str]] = None
    answer: str
    hints: list[str]
    explanation: Optional[str] = None
    difficulty: CardDifficulty
    # Gemini rejects nested structured `display` objects ("too many states").
    # Pass layout as a JSON *string*; the server parses it into `display`.
    # Example: '{"type":"column_math","operator":"+","operands":["42","35"]}'
    display_json: Optional[str] = None

    @field_validator("hints")
    @classmethod
    def hints_nonempty(cls, v: list[str]) -> list[str]:
        cleaned = [h.strip() for h in v if h and str(h).strip()]
        if not cleaned:
            raise ValueError("hints must include at least one non-empty hint")
        return cleaned

    @model_validator(mode="after")
    def options_match_type(self) -> "StudyCardOut":
        if self.question_type in ("multiple_choice", "true_false"):
            if not self.options or len(self.options) < 2:
                raise ValueError(f"{self.question_type} requires at least 2 options")
            if self.answer not in self.options:
                # Soft fix: allow answer text that matches an option case-insensitively
                lowered = {o.lower(): o for o in self.options}
                key = self.answer.lower().strip()
                if key in lowered:
                    self.answer = lowered[key]
                else:
                    raise ValueError("answer must be one of the options for MCQ/true_false")
        return self


class StudyDeckOut(BaseModel):
    # Keep schema simple for model-serving (avoid list length constraints).
    cards: list[StudyCardOut]
