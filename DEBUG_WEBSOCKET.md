# Debugging WebSocket HTTP 500 Error

## Quick Checks

1. **Is the server running with Daphne?**
   ```bash
   # Check running processes
   ps aux | grep daphne
   
   # If not running, start it:
   poetry run daphne -b 0.0.0.0 -p 8000 backend.asgi:application
   ```

2. **Check Django server logs** - Look for the actual error when connecting

3. **Verify Redis/Channel Layer:**
   ```bash
   # Check if Redis is running (if not using in-memory)
   redis-cli ping
   
   # Or set USE_INMEMORY_CHANNELS=true in .env
   ```

4. **Check if prompt exists in database:**
   ```bash
   poetry run python manage.py shell
   >>> from ai.models import AIPrompt
   >>> AIPrompt.objects.filter(prompt_type='course_generation', is_active=True).exists()
   ```

5. **Test ASGI application directly:**
   ```bash
   poetry run python -c "from backend.asgi import application; print('ASGI OK')"
   ```

## Common Issues

1. **Server running with `runserver` instead of `daphne`**
   - `runserver` doesn't support WebSockets
   - Must use `daphne` or `uvicorn`

2. **Missing prompt in database**
   - Run: `poetry run python manage.py init_default_prompts`

3. **Channel layer not configured**
   - Check `USE_INMEMORY_CHANNELS` in settings
   - Or verify Redis connection

4. **Import errors in consumer**
   - Check if all imports work: `poetry run python -c "from ai.consumers import CourseGenerationConsumer"`

