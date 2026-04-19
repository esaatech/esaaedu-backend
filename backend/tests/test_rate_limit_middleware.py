"""Tests for global rate limit middleware."""

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings


_TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "rate_limit_middleware_tests",
    }
}


@override_settings(
    CACHES=_TEST_CACHES,
    RATE_LIMIT_ENABLED=True,
    RATE_LIMIT_REQUESTS_PER_WINDOW=5,
    RATE_LIMIT_WINDOW_SECONDS=60,
)
class RateLimitMiddlewareTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_exempt_path_not_rate_limited(self):
        for _ in range(20):
            r = self.client.get("/health/")
            self.assertEqual(r.status_code, 200)

    def test_non_exempt_path_returns_429_after_limit(self):
        for _ in range(5):
            r = self.client.get("/")
            self.assertEqual(r.status_code, 200)
        r = self.client.get("/")
        self.assertEqual(r.status_code, 429)
        data = r.json()
        self.assertIn("error", data)
        self.assertEqual(r["Retry-After"], "60")

    @override_settings(RATE_LIMIT_ENABLED=False)
    def test_disabled_allows_unlimited(self):
        for _ in range(10):
            r = self.client.get("/")
            self.assertEqual(r.status_code, 200)
