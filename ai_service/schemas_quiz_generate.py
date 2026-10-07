"""Structured output for quiz generation (MC + true/false)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


def _option_texts(options: Any) -> list[str]:
    if not isinstance(options, list):
        return []
    texts: list[str] = []
    for opt in options:
        if isinstance(opt, str) and opt.strip():
            texts.append(opt.strip())
        elif isinstance(opt, dict):
            for key in ("text", "label", "value", "option", "answer"):
                raw = opt.get(key)
                if isinstance(raw, str) and raw.strip():
                    texts.append(raw.strip())
                    break
        elif opt is not None:
            s = str(opt).strip()
            if s:
                texts.append(s)
    return texts


class QuizQuestionOut(BaseModel):
    """
    Flat fields (like Study Coach cards). Nested content.dict was causing
    Gemini structured-output retries to fail even when options were present.
    Server maps options/correct_answer into content for the teacher API.
    """

    question_text: str = Field(description="The question text shown to the student")
    type: Literal["multiple_choice", "true_false"] = Field(
        description="Question type: multiple_choice or true_false"
    )
    points: int = Field(default=1, ge=1, description="Points awarded for this question")
    options: list[str] = Field(
        default_factory=list,
        description=(
            "For multiple_choice: at least 2 answer choices as plain strings "
            "(prefer 4). For true_false: use [\"True\", \"False\"] or leave empty."
        ),
    )
    correct_answer: str = Field(
        default="",
        description=(
            "For multiple_choice: exact text of the correct option. "
            "For true_false: 'true' or 'false'."
        ),
    )
    explanation: str = Field(
        default="",
        description="Short explanation shown after answering",
    )
    # Optional legacy nested bag — accepted but not required
    content: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional; prefer top-level options and correct_answer",
    )

    @field_validator("question_text", "explanation", "correct_answer")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return (value or "").strip()

    @field_validator("options", mode="before")
    @classmethod
    def coerce_options(cls, value: Any) -> list[str]:
        return _option_texts(value)

    @model_validator(mode="after")
    def require_mc_options(self) -> "QuizQuestionOut":
        if self.type != "multiple_choice":
            return self
        opts = list(self.options or [])
        if len(opts) < 2 and isinstance(self.content, dict):
            opts = _option_texts(self.content.get("options"))
            if len(opts) >= 2:
                self.options = opts
        if len(opts) < 2:
            raise ValueError(
                "multiple_choice requires at least 2 string options "
                'e.g. options=["A","B","C","D"], correct_answer="A"'
            )
        if self.correct_answer:
            lowered = {o.lower(): o for o in self.options}
            key = self.correct_answer.lower().strip()
            if key in lowered:
                self.correct_answer = lowered[key]
        return self


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
