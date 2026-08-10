"""Helpers to load AIService / AIPromptConfiguration rows."""

from __future__ import annotations

from typing import Optional

from .models import AIPromptConfiguration, AIService


def get_ai_service(slug: str) -> Optional[AIService]:
    return AIService.objects.filter(slug=slug, is_active=True).first()


def get_default_prompt_config(service_slug: str) -> Optional[AIPromptConfiguration]:
    service = get_ai_service(service_slug)
    if not service:
        return None
    return service.get_default_prompt()


def get_prompt_config(
    service_slug: str,
    prompt_slug: str = "default",
) -> Optional[AIPromptConfiguration]:
    return (
        AIPromptConfiguration.objects.filter(
            service__slug=service_slug,
            service__is_active=True,
            slug=prompt_slug,
            is_active=True,
        )
        .select_related("ai_model", "service")
        .first()
    )
