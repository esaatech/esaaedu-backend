"""Tests for Gemini error classification and user-facing messages."""
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from google.api_core.exceptions import NotFound, ResourceExhausted

from unittest.mock import MagicMock, patch

from ai.exceptions import (
    USER_FACING_AI_ERROR,
    GeminiServiceError,
    from_exception,
    from_google_api_error,
)
from ai.api_errors import ai_error_response
from ai.gemini_service import (
    GeminiService,
    _extract_response_text,
    _extract_text_parts,
    _parse_structured_response,
    _raise_gemini_error,
)

LOC_MEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}


def _make_multi_part_response(part_texts):
    """Build a mock Gemini response with multiple text parts."""
    parts = []
    for text in part_texts:
        part = MagicMock()
        part.function_call = None
        part.text = text
        parts.append(part)

    content = MagicMock()
    content.parts = parts

    candidate = MagicMock()
    candidate.content = content

    response = MagicMock()
    response.candidates = [candidate]
    response.text = property(
        lambda self: (_ for _ in ()).throw(
            ValueError(
                "Cannot get the Candidate text. Multiple content parts are not supported."
            )
        )
    )
    type(response).text = property(
        lambda self: (_ for _ in ()).throw(
            ValueError(
                "Cannot get the Candidate text. Multiple content parts are not supported."
            )
        )
    )
    return response


@override_settings(CACHES=LOC_MEM_CACHE)
class GeminiExceptionsTests(SimpleTestCase):
    def test_not_found_maps_to_model_unavailable(self):
        err = from_google_api_error(NotFound("Publisher Model not found"))
        self.assertEqual(err.error_code, "model_unavailable")
        self.assertTrue(err.notify_admin)

    def test_rate_limit_does_not_notify_admin(self):
        err = from_google_api_error(ResourceExhausted("quota"))
        self.assertEqual(err.error_code, "rate_limited")
        self.assertFalse(err.notify_admin)

    def test_improperly_configured_maps_to_ai_not_configured(self):
        err = from_exception(ImproperlyConfigured("GEMINI_MODEL required"))
        self.assertEqual(err.error_code, "ai_not_configured")

    def test_ai_error_response_hides_technical_detail_in_production(self):
        exc = from_google_api_error(NotFound("projects/foo/models/bar"))
        with override_settings(DEBUG=False):
            response = ai_error_response(
                exc,
                context="test",
                endpoint="/test/",
            )
        self.assertEqual(response.data["error"], USER_FACING_AI_ERROR)
        self.assertNotIn("projects/foo", response.data["error"])

    def test_ai_error_response_shows_technical_detail_in_debug(self):
        exc = from_google_api_error(NotFound("projects/foo/models/bar"))
        with override_settings(DEBUG=True):
            response = ai_error_response(
                exc,
                context="test",
                endpoint="/test/",
            )
        self.assertIn("projects/foo", response.data["error"])
        self.assertEqual(response.data["error_code"], "model_unavailable")

    @patch("error_alerts.notify_ai_failure")
    def test_raise_gemini_error_notifies_once(self, mock_notify):
        from ai.exceptions import GeminiServiceError
        from ai.gemini_service import _raise_gemini_error

        err = from_google_api_error(NotFound("model missing"))
        with self.assertRaises(GeminiServiceError):
            _raise_gemini_error(err, context="GeminiService.generate")
        mock_notify.assert_called_once()
        self.assertTrue(err.slack_notified)

    @patch("error_alerts.notify_ai_failure")
    def test_ai_error_response_skips_duplicate_slack_when_already_notified(self, mock_notify):
        exc = from_google_api_error(NotFound("projects/foo/models/bar"))
        exc.slack_notified = True
        with override_settings(DEBUG=False):
            ai_error_response(exc, context="test", endpoint="/test/")
        mock_notify.assert_not_called()


@override_settings(CACHES=LOC_MEM_CACHE)
class GeminiServiceResponseExtractionTests(SimpleTestCase):
    def test_extract_text_parts_from_multi_part_response(self):
        part1 = '```json\n{"points_earned": 8, "feedback": "Good"}\n```'
        part2 = '```json\n{"points_earned": 8, "feedback": "Good", "confidence": 0.95}\n```'
        response = _make_multi_part_response([part1, part2])

        parts = _extract_text_parts(response)
        self.assertEqual(len(parts), 2)
        self.assertIn("points_earned", parts[0])
        self.assertIn("confidence", parts[1])

    def test_extract_response_text_uses_last_part_when_multiple(self):
        part1 = '{"points_earned": 8}'
        part2 = '{"points_earned": 8, "confidence": 0.95}'
        response = _make_multi_part_response([part1, part2])

        text = _extract_response_text(response)
        self.assertEqual(text, part2)

    def test_parse_structured_response_prefers_last_valid_json_part(self):
        part1 = '```json\n{"points_earned": 8, "feedback": "Good"}\n```'
        part2 = '```json\n{"points_earned": 8, "feedback": "Good", "confidence": 0.95}\n```'

        parsed = _parse_structured_response(part2, [part1, part2])

        self.assertEqual(parsed["points_earned"], 8)
        self.assertEqual(parsed["confidence"], 0.95)

    def test_parse_structured_response_raises_on_invalid_json(self):
        with self.assertRaises(Exception):
            _parse_structured_response("not json", ["also not json"])


@override_settings(CACHES=LOC_MEM_CACHE)
class GeminiServiceGenerateTests(SimpleTestCase):
    GRADING_SCHEMA = {
        "type": "object",
        "properties": {
            "points_earned": {"type": "number"},
            "feedback": {"type": "string"},
            "correct_answer": {"type": "string"},
            "confidence": {"type": "number"},
        },
        "required": ["points_earned", "feedback", "correct_answer"],
    }

    def _mock_service(self):
        with patch.object(GeminiService, "__init__", lambda self: None):
            service = GeminiService()
            service.project_id = "test-project"
            service.location = "us-central1"
            service.model_name = "gemini-2.5-flash"
            return service

    @patch("ai.gemini_service.resolve_model_name", return_value="gemini-2.5-flash")
    @patch.object(GeminiService, "_get_model")
    def test_generate_parses_multi_part_structured_response(self, mock_get_model, _mock_resolve):
        part1 = '```json\n{"points_earned": 8, "feedback": "Good start", "correct_answer": "Model"}\n```'
        part2 = (
            '```json\n'
            '{"points_earned": 8, "feedback": "Good start", '
            '"correct_answer": "Model", "confidence": 0.95}\n'
            '```'
        )
        mock_model = MagicMock()
        mock_model.generate_content.return_value = _make_multi_part_response([part1, part2])
        mock_get_model.return_value = mock_model

        service = self._mock_service()
        result = service.generate(
            system_instruction="You are a grader.",
            prompt="Grade this answer.",
            response_schema=self.GRADING_SCHEMA,
            temperature=0.3,
        )

        self.assertEqual(result["parsed"]["points_earned"], 8)
        self.assertEqual(result["parsed"]["confidence"], 0.95)
        self.assertIn("confidence", result["raw"])

    @patch("ai.gemini_service.resolve_model_name", return_value="gemini-2.5-flash")
    @patch.object(GeminiService, "_get_model")
    def test_generate_parses_single_part_structured_response(self, mock_get_model, _mock_resolve):
        part = '{"points_earned": 10, "feedback": "Excellent", "correct_answer": "Full model"}'
        mock_model = MagicMock()
        mock_model.generate_content.return_value = _make_multi_part_response([part])
        mock_get_model.return_value = mock_model

        service = self._mock_service()
        result = service.generate(
            system_instruction="You are a grader.",
            prompt="Grade this answer.",
            response_schema=self.GRADING_SCHEMA,
            temperature=0.3,
        )

        self.assertEqual(result["parsed"]["points_earned"], 10)
        self.assertEqual(result["parsed"]["feedback"], "Excellent")

    @patch("error_alerts.notify_ai_failure")
    @patch("ai.gemini_service.resolve_model_name", return_value="gemini-2.5-flash")
    @patch.object(GeminiService, "_get_model")
    def test_generate_raises_on_invalid_json(
        self, mock_get_model, _mock_resolve, mock_notify
    ):
        mock_model = MagicMock()
        mock_model.generate_content.return_value = _make_multi_part_response(
            ["not valid json", "still not json"]
        )
        mock_get_model.return_value = mock_model

        service = self._mock_service()
        with self.assertRaises(GeminiServiceError) as ctx:
            service.generate(
                system_instruction="You are a grader.",
                prompt="Grade this answer.",
                response_schema=self.GRADING_SCHEMA,
                temperature=0.3,
            )

        self.assertEqual(ctx.exception.error_code, "invalid_response")
        mock_notify.assert_called_once_with(
            error_code="invalid_response",
            log_message=ctx.exception.log_message,
            context="GeminiService.generate",
            notify_admin=False,
        )
