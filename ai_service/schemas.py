"""Shared Pydantic output schemas for ai_service runners."""

from pydantic import BaseModel, Field


class GatewayProbeResult(BaseModel):
    """Minimal structured output for the Phase 2 gateway playground."""

    ok: bool = Field(description="Whether the probe succeeded from the model's perspective")
    echo: str = Field(description="Short echo / confirmation message")
    notes: str = Field(default="", description="Optional extra notes")
