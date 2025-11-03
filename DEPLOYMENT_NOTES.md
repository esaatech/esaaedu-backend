# Deployment Notes: Django Channels Migration

## Server Changes

### Before (WSGI - HTTP only)
- **Development**: `python manage.py runserver` ✅ (supports both WSGI/ASGI)
- **Production**: `gunicorn` ❌ (WSGI only, cannot handle WebSockets)

### After (ASGI - HTTP + WebSocket)
- **Development**: `python manage.py runserver` ✅ (still works, uses ASGI)
- **Production**: `daphne` ✅ (ASGI server, handles HTTP + WebSocket)

## Why the Change?

**Gunicorn limitations:**
- Only supports WSGI protocol (HTTP requests)
- Cannot handle WebSocket connections
- Cannot handle async/await patterns

**Daphne benefits:**
- Supports ASGI protocol (HTTP + WebSocket)
- Handles WebSocket connections natively
- Full async support
- Recommended by Django Channels team
- Backward compatible (still handles all HTTP requests)

## Alternative: Uvicorn

You can also use `uvicorn` instead of `daphne`:
```bash
CMD ["uvicorn", "backend.asgi:application", "--host", "0.0.0.0", "--port", "8080"]
```

**Recommendation:** Use `daphne` - it's maintained by the Channels team and optimized for Django.

## Cloud Run Considerations

- Cloud Run supports WebSocket connections ✅
- No changes needed to Cloud Run configuration
- Same port (8080) handles both HTTP and WebSocket
- Load balancer automatically upgrades HTTP to WebSocket when needed

## Testing

### Local Development
```bash
# Using Django's runserver (supports ASGI)
poetry run python manage.py runserver

# OR using Daphne directly
poetry run daphne -b 0.0.0.0 -p 8000 backend.asgi:application
```

### Production
- Dockerfile now uses Daphne instead of Gunicorn
- No other deployment changes needed

## Redis for Channel Layers

**Production:**
- Use Redis instance (Google Cloud Memorystore or managed Redis)
- Set `REDIS_URL` environment variable

**Development:**
- Can use `USE_INMEMORY_CHANNELS=true` for local testing
- OR run local Redis: `docker run -p 6379:6379 redis`

## Performance Notes

- Daphne is single-threaded per worker (like Gunicorn)
- For high concurrency, Cloud Run auto-scales containers
- Each container can handle multiple WebSocket connections
- Consider Redis connection pooling for high traffic


