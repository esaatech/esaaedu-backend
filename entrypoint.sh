#!/bin/bash
set -e

echo "🚀 Starting application..."

# Run database migrations
echo "📦 Running database migrations..."
python manage.py migrate --noinput

# Optional AI catalog seeds (idempotent). Enable with AI_SERVICE_SEED_ON_STARTUP=true
SEED_FLAG="${AI_SERVICE_SEED_ON_STARTUP:-false}"
if [[ "${SEED_FLAG}" == "true" || "${SEED_FLAG}" == "1" || "${SEED_FLAG}" == "yes" ]]; then
  echo "🤖 Seeding AI Service catalog (setup_ai_models / setup_study_coach_deck / setup_study_coach_grade)..."
  python manage.py setup_ai_models
  python manage.py setup_study_coach_deck
  python manage.py setup_study_coach_grade
fi

# Start the application
echo "✅ Starting Daphne server..."
exec daphne -b 0.0.0.0 -p "$PORT" --verbosity 2 backend.asgi:application
