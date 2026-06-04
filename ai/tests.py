"""Tests for Gemini error classification and user-facing messages."""
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from google.api_core.exceptions import NotFound, ResourceExhausted

from ai.exceptions import (
    USER_FACING_AI_ERROR,
    from_exception,
    from_google_api_error,
)
from ai.api_errors import ai_error_response

LOC_MEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}


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
