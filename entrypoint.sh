#!/bin/bash
set -e

echo "🚀 Starting application..."

# Run database migrations
echo "📦 Running database migrations..."
python manage.py migrate --noinput

# Start the application
echo "✅ Starting Daphne server..."
exec daphne -b 0.0.0.0 -p "$PORT" --verbosity 2 backend.asgi:application

