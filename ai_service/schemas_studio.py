"""Structured output for the Studio system-instruction rewriter."""

from pydantic import BaseModel, Field


class StudioSystemInstructionOut(BaseModel):
    system_prompt: str = Field(min_length=20, max_length=20000)
    summary: str = Field(min_length=1, max_length=400)
