"""Structured output for assessment (test/exam) generation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ai_service.schemas_quiz_generate import _option_texts

QuestionType = Literal[
    "multiple_choice",
    "true_false",
    "fill_blank",
    "short_answer",
    "essay",
    "code",
]

MAX_STARTER_LINES = 20
MAX_STARTER_CHARS = 800


def _clean_starter_code(value: Any) -> str:
    text = str(value or "").replace("\r\n", "\n").strip()
    if not text:
        return ""
    kept: list[str] = []
    blank_run = 0
    for line in text.split("\n"):
        if not line.strip():
            blank_run += 1
            if blank_run > 1:
                continue
            kept.append("")
        else:
            blank_run = 0
            kept.append(line.rstrip())
    if len(kept) > MAX_STARTER_LINES:
        kept = kept[:MAX_STARTER_LINES]
    text = "\n".join(kept).strip()
    if len(text) > MAX_STARTER_CHARS:
        text = text[:MAX_STARTER_CHARS].rstrip()
    return text


def _string_list(value: Any) -> list[str]:
    if isinstance(value, dict):
        items = list(value.values())
    elif isinstance(value, list):
        items = value
    elif isinstance(value, str) and value.strip():
        items = [part.strip() for part in value.split(",")]
    else:
        return []
    texts: list[str] = []
    for item in items:
        if isinstance(item, str) and item.strip():
            texts.append(item.strip())
        elif item is not None and str(item).strip():
            texts.append(str(item).strip())
    return texts


class AssessmentQuestionOut(BaseModel):
    """
    Flat fields so structured output does not nest options or starter code
    inside a free-form content object.
    """

    question_text: str = Field(description="The question text shown to the student")
    type: QuestionType = Field(description="Question type")
    points: int = Field(default=1, ge=1, description="Points awarded for this question")
    explanation: str = Field(
        description="Required. Why the correct answer is right, or what a complete response includes."
    )
    options: list[str] = Field(
        default_factory=list,
        description="multiple_choice only: at least 2 plain-string choices, prefer 4.",
    )
    correct_answer: str = Field(
        default="",
        description=(
            "multiple_choice: exact option text. true_false: true or false. "
            "essay and short_answer: the model answer. Leave empty for fill_blank and code."
        ),
    )
    blanks: list[str] = Field(
        default_factory=list,
        description="fill_blank only: the sentence pieces or blank placeholders.",
    )
    correct_answers: list[str] = Field(
        default_factory=list,
        description="fill_blank only: one expected answer per blank, in order.",
    )
    language: str = Field(
        default="",
        description="code only: programming language, usually python.",
    )
    instructions: str = Field(
        default="",
        description="essay or code: instructions shown to the student.",
    )
    starter_code: str = Field(
        default="",
        description=(
            "code only: a short scaffold of at most 20 lines. "
            "Do not pad with blank lines."
        ),
    )

    @field_validator("question_text", "explanation", "correct_answer", "language", "instructions")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return (value or "").strip()

    @field_validator("options", mode="before")
    @classmethod
    def coerce_options(cls, value: Any) -> list[str]:
        return _option_texts(value)

    @field_validator("blanks", "correct_answers", mode="before")
    @classmethod
    def coerce_lists(cls, value: Any) -> list[str]:
        return _string_list(value)

    @field_validator("starter_code", mode="before")
    @classmethod
    def cap_starter_code(cls, value: Any) -> str:
        return _clean_starter_code(value)

    @model_validator(mode="after")
    def require_answer(self) -> "AssessmentQuestionOut":
        if not (self.explanation or "").strip():
            raise ValueError("explanation is required for every question")
        if self.type == "multiple_choice":
            if len(self.options) < 2:
                raise ValueError("multiple_choice requires at least 2 string options")
            lowered = {opt.lower(): opt for opt in self.options}
            key = (self.correct_answer or "").lower().strip()
            if key not in lowered:
                raise ValueError("multiple_choice correct_answer must match an option")
            self.correct_answer = lowered[key]
        elif self.type == "true_false":
            key = (self.correct_answer or "").lower().strip()
            if key not in ("true", "false"):
                raise ValueError("true_false correct_answer must be true or false")
            self.correct_answer = key
        elif self.type == "fill_blank":
            if not self.correct_answers:
                raise ValueError("fill_blank requires correct_answers")
        elif self.type in ("essay", "short_answer"):
            if not (self.correct_answer or "").strip():
                raise ValueError(f"{self.type} requires correct_answer")
        elif self.type == "code":
            if not (self.instructions or "").strip():
                raise ValueError("code requires instructions")
            if not (self.language or "").strip():
                self.language = "python"
        return self


class AssessmentGenerateOut(BaseModel):
    title: str = Field(description="Assessment title")
    description: str = Field(default="", description="Short description")
    questions: list[AssessmentQuestionOut] = Field(description="Generated questions")

    @field_validator("title", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return (value or "").strip()
