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
    question_text: str = Field(description="The question text shown to the student")
    type: Literal["multiple_choice", "true_false"] = Field(
        description="Question type: multiple_choice or true_false"
    )
    points: int = Field(default=1, ge=1, description="Points awarded for this question")
    content: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Question-specific content. For multiple_choice REQUIRED: "
            '{"options": ["option A","option B","option C","option D"], '
            '"correct_answer": "exact text of the correct option"}. '
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

    @model_validator(mode="after")
    def require_mc_options(self) -> "QuizQuestionOut":
        if self.type != "multiple_choice":
            return self
        content_opts = (
            self.content.get("options") if isinstance(self.content, dict) else None
        )
        texts = _option_texts(content_opts)
        if len(texts) < 2:
            texts = _option_texts(self.options)
        if len(texts) < 2:
            raise ValueError(
                "multiple_choice questions must include at least 2 string options "
                'in content.options, e.g. content={"options": ["A","B","C","D"], '
                '"correct_answer": "A"}'
            )
        return self


class QuizGenerateOut(BaseModel):
    title: str = Field(description="Quiz title")
    description: str = Field(default="", description="Quiz description")
    questions: list[QuizQuestionOut] = Field(
        min_length=1,
        description="List of quiz questions (multiple_choice and true_false only)",
    )

    @field_validator("title", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return (value or "").strip()
