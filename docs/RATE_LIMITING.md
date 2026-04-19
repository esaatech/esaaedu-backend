# Global HTTP rate limiting

This document describes the application-layer rate limiting added for the Little Learners Tech API: behavior, configuration, cache requirements, and operations.

## Goals

- Apply a **baseline limit per client IP** across most HTTP routes handled by Django.
- **Skip** routes that must not be throttled (webhooks, health checks, static/media).
- Use a **shared cache** in production so limits are consistent across multiple processes (e.g. Cloud Run instances).
- **Fail open** when the cache/Redis is unavailable so the API stays available (limits are skipped until cache works).

Separate, **endpoint-specific** limits (for example the student IDE “explain” AI endpoints) remain implemented in view code using the same cache pattern; they are not covered by this middleware’s global counter.

## Components

| Piece | Location |
|-------|----------|
| Middleware | [`backend/rate_limit_middleware.py`](../backend/rate_limit_middleware.py) |
| Middleware registration | [`backend/settings.py`](../backend/settings.py) (`MIDDLEWARE`, after Firebase auth middleware) |
| Django cache (Redis or locmem) | [`backend/settings.py`](../backend/settings.py) (`CACHES`) |
| Tests | [`backend/tests/test_rate_limit_middleware.py`](../backend/tests/test_rate_limit_middleware.py) |
| Example env vars | [`env.example`](../env.example) |

## How it works

1. **`RateLimitMiddleware`** runs on each request (unless disabled or path-exempt).
2. The client is identified by **IP**:
   - If `HTTP_X_FORWARDED_FOR` is present (typical behind a proxy/load balancer), the **first** comma-separated value is used.
   - Otherwise `REMOTE_ADDR` is used, or `"unknown"` if missing.
3. A **fixed-window** counter in Django’s **default cache** tracks requests per IP:
   - Cache key pattern: `rl:mw:v1:ip:<client_ip>` (prefixed by Django’s cache `KEY_PREFIX` when using Redis, e.g. `llt`).
   - Window length: `RATE_LIMIT_WINDOW_SECONDS` (default **60** seconds).
   - Max requests per window: `RATE_LIMIT_REQUESTS_PER_WINDOW` (default **500**).
4. If the count would exceed the limit, the middleware returns **HTTP 429** with a JSON body and a **`Retry-After`** header set to the window length in seconds.
5. If **any** cache operation raises an unexpected error, behavior is **fail open** (request is allowed). Redis connection/DNS failures are logged at **debug** level without printing a full traceback on every request.

## Algorithm (fixed window)

The implementation matches the pattern used elsewhere (e.g. student IDE explain helpers): first request in a window creates the key with TTL; subsequent requests increment until the count reaches the limit. This is a simple fixed window, not a sliding window.

## Django cache and Redis

- If **`REDIS_URL`** is set (non-empty), `CACHES['default']` uses **`django-redis`** so counters are shared across all app instances.
- If **`REDIS_URL`** is unset, **`LocMemCache`** is used (per-process only). That is fine for local development and tests but **not** for accurate global limits under multiple Gunicorn workers or Cloud Run replicas.

**Local development:** If `REDIS_URL` points at a remote host that does not resolve (e.g. Upstash while offline), the middleware fails open and rate limiting effectively does not apply until Redis is reachable or you use a local Redis URL / leave `REDIS_URL` unset for locmem.

## Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `REDIS_URL` | *(empty)* | When set, enables Redis-backed `CACHES['default']` (shared counters). |
| `RATE_LIMIT_ENABLED` | `true` | Set to `false` to disable the middleware entirely (e.g. temporary debugging). |
| `RATE_LIMIT_REQUESTS_PER_WINDOW` | `500` | Max requests per IP per window. |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Window size in seconds. |
| `RATE_LIMIT_EXEMPT_PREFIXES` | *(see below)* | Comma-separated URL path prefixes **not** rate limited. If unset or empty, built-in defaults apply. |

Default exempt prefixes (when `RATE_LIMIT_EXEMPT_PREFIXES` is not set):

- `/api/webhooks/` — Twilio and other inbound webhooks
- `/api/billing/webhooks/` — Stripe webhooks
- `/health/` — Health check
- `/static/` — Static files (if routed through Django)
- `/media/` — Media files (if routed through Django)

Paths are matched with **`startswith`**, so `/api/webhooks/twilio/sms/` is covered by `/api/webhooks/`.

## HTTP 429 response

```json
{
  "error": "Too many requests",
  "detail": "Rate limit exceeded. Try again later."
}
```

Header: `Retry-After: <RATE_LIMIT_WINDOW_SECONDS>` (string).

Clients (and Stripe/Twilio) are **not** expected to hit these limits on exempt routes; tune `RATE_LIMIT_*` if legitimate SPA traffic behind one NAT IP approaches the default.

## Middleware order

`RateLimitMiddleware` is registered **after** `authentication.middleware.FirebaseAuthenticationMiddleware` so the rest of the stack runs in a sensible order; the limiter itself keys only on IP, not on user.

## Tests

`backend/tests/test_rate_limit_middleware.py` uses **`SimpleTestCase`** and overrides **`CACHES`** to locmem so tests do not require Redis. It covers:

- Exempt paths are not limited.
- Non-exempt paths return 429 after the configured limit.
- `RATE_LIMIT_ENABLED=False` allows unlimited requests.

Run:

```bash
poetry run pytest backend/tests/test_rate_limit_middleware.py -q
```

## Tuning and operations

- **Stricter API-only limits** or **per-user** JWT limits are not part of this middleware; consider DRF throttles on specific views if needed.
- **Edge/WAF** rate limits (e.g. Cloud Armor, CDN) can complement this layer; they operate before the app.
- Adjust **`RATE_LIMIT_REQUESTS_PER_WINDOW`** / **`RATE_LIMIT_WINDOW_SECONDS`** for your traffic profile (e.g. busy dashboards issuing many parallel API calls from one office IP).

## Related code

- Student IDE AI explain endpoints use a separate per-user cache limit in `student/views.py` (`_ide_explain_rate_limit_ok`), not the global IP middleware.
