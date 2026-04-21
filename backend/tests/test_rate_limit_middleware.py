"""Tests for global rate limit middleware."""

from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from backend.rate_limit_middleware import fixed_window_allow


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


@override_settings(CACHES=_TEST_CACHES)
class FixedWindowAllowFailOpenTests(SimpleTestCase):
    """Same pattern as student IDE explain rate limit — must not 500 when Redis/cache fails."""

    def setUp(self):
        cache.clear()

    def test_cache_add_raises_fails_open(self):
        with patch(
            "backend.rate_limit_middleware.cache.add",
            side_effect=OSError("Error -2 connecting to redis: Name or service not known"),
        ):
            self.assertTrue(fixed_window_allow("rl:test", 5, 60))

    def test_cache_incr_raises_fails_open(self):
        """After add returns False, get/incr path must also fail open."""
        with patch(
            "backend.rate_limit_middleware.cache.add",
            return_value=False,
        ), patch(
            "backend.rate_limit_middleware.cache.get",
            return_value=1,
        ), patch(
            "backend.rate_limit_middleware.cache.incr",
            side_effect=OSError("connection refused"),
        ):
            self.assertTrue(fixed_window_allow("rl:test2", 5, 60))
