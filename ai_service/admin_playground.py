"""Shared helpers for Admin AI playgrounds (Jobeasy-style Run AJAX)."""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse, HttpResponseNotAllowed
from django.urls import path
from django.utils import timezone


def json_response(payload: dict[str, Any], status: int = 200) -> HttpResponse:
    return HttpResponse(
        json.dumps(payload, cls=DjangoJSONEncoder),
        status=status,
        content_type="application/json",
    )


class AIPlaygroundAdminMixin:
    """
    Mixin for ModelAdmin playgrounds.

    Subclasses set:
      - playground_runner: callable(**inputs) -> dict with success key
      - playground_input_fields: list of POST field names copied from the form
      - prompt_config_field: name of FK field on the model (default prompt_config)
    """

    playground_runner: Optional[Callable[..., dict[str, Any]]] = None
    playground_input_fields: tuple[str, ...] = ()
    prompt_config_field: str = "prompt_config"
    change_form_template = None  # set per admin

    def get_urls(self):
        urls = super().get_urls()
        opts = self.model._meta
        basename = f"{opts.app_label}_{opts.model_name}"
        extra = [
            path(
                "run-preview/",
                self.admin_site.admin_view(self.run_preview),
                name=f"{basename}_run_preview",
            ),
            path(
                "<path:object_id>/persist-run/",
                self.admin_site.admin_view(self.persist_run),
                name=f"{basename}_persist_run",
            ),
        ]
        return extra + urls

    def _user_can_run(self, request) -> bool:
        opts = self.model._meta
        return request.user.has_perm(
            f"{opts.app_label}.add_{opts.model_name}"
        ) or request.user.has_perm(f"{opts.app_label}.change_{opts.model_name}")

    def _resolve_prompt_config(self, request):
        from ai_service.models import AIPromptConfiguration

        raw = (request.POST.get(self.prompt_config_field) or "").strip()
        if raw.isdigit():
            return AIPromptConfiguration.objects.filter(pk=int(raw)).select_related(
                "ai_model", "service"
            ).first()
        return None

    def _collect_inputs(self, request) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for name in self.playground_input_fields:
            data[name] = (request.POST.get(name) or "").strip()
        data["prompt_config"] = self._resolve_prompt_config(request)
        return data

    def run_preview(self, request):
        """POST: run playground without requiring Save first."""
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not self._user_can_run(request):
            return json_response({"success": False, "error": "Permission denied"}, status=403)
        if self.playground_runner is None:
            return json_response(
                {"success": False, "error": "No playground_runner configured"},
                status=500,
            )

        inputs = self._collect_inputs(request)
        try:
            result = self.playground_runner(**inputs)
        except TypeError:
            # Allow runners that take explicit kwargs matching field names
            result = self.playground_runner(
                **{k: v for k, v in inputs.items() if k != "prompt_config"},
                prompt_config=inputs.get("prompt_config"),
            )
        except Exception as exc:
            return json_response({"success": False, "error": str(exc)}, status=500)

        if not isinstance(result, dict):
            return json_response(
                {"success": False, "error": "Runner must return a dict"},
                status=500,
            )
        return json_response(result)

    def persist_run(self, request, object_id):
        """POST: write last preview payload onto the saved playground row."""
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not self._user_can_run(request):
            return json_response({"success": False, "error": "Permission denied"}, status=403)

        obj = self.get_object(request, object_id)
        if obj is None:
            return json_response({"success": False, "error": "Not found"}, status=404)

        raw = request.POST.get("pending_result") or ""
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return json_response({"success": False, "error": "Invalid pending_result JSON"}, status=400)

        if not isinstance(payload, dict):
            return json_response({"success": False, "error": "pending_result required"}, status=400)

        self.apply_run_result(obj, payload)
        obj.save()
        return json_response({"success": True, "id": obj.pk})

    def apply_run_result(self, obj, payload: dict[str, Any]) -> None:
        """Map runner payload onto playground model fields. Override per admin if needed."""
        obj.succeeded = bool(payload.get("success"))
        obj.error_message = (payload.get("error") or "") if not obj.succeeded else ""
        obj.result_json = payload.get("result")
        obj.provider = payload.get("provider") or ""
        obj.model_id = payload.get("model_id") or ""
        temp = payload.get("temperature")
        obj.temperature = temp if temp is not None else None
        obj.instruction_slug = payload.get("instruction_slug") or ""
        obj.raw_response_text = payload.get("raw_text") or ""
        obj.last_run_at = timezone.now()
