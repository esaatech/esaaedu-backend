from django.test import SimpleTestCase, override_settings

from ai_service.config import resolve_generation_settings


class ResolveGenerationSettingsTests(SimpleTestCase):
    @override_settings(GEMINI_MODEL="gemini-2.5-flash")
    def test_defaults_to_gemini_from_env(self):
        settings = resolve_generation_settings()
        self.assertEqual(settings.provider, "gemini")
        self.assertTrue(settings.model_id)

    def test_explicit_openai_override(self):
        settings = resolve_generation_settings(
            provider="openai",
            model_id="gpt-4o-mini",
            temperature=0.2,
        )
        self.assertEqual(settings.provider, "openai")
        self.assertEqual(settings.model_id, "gpt-4o-mini")
        self.assertEqual(settings.temperature, 0.2)

    def test_rejects_unknown_provider(self):
        with self.assertRaises(ValueError):
            resolve_generation_settings(provider="anthropic")
