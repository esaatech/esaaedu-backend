#!/bin/bash
set -e

echo "🚀 Starting application..."

# Run database migrations
echo "📦 Running database migrations..."
python manage.py migrate --noinput

# Optional AI catalog seeds (idempotent). Enable with AI_SERVICE_SEED_ON_STARTUP=true
SEED_FLAG="${AI_SERVICE_SEED_ON_STARTUP:-false}"
if [[ "${SEED_FLAG}" == "true" || "${SEED_FLAG}" == "1" || "${SEED_FLAG}" == "yes" ]]; then
  echo "🤖 Seeding AI Service catalog (setup_ai_models / study_coach / tutorx / teacher / assessment / quiz / assignment / studio)..."
  python manage.py setup_ai_models
  python manage.py setup_study_coach_deck
  python manage.py setup_study_coach_grade
  python manage.py setup_tutorx_assignment_grade
  python manage.py setup_teacher_assignment_grade
  python manage.py setup_assessment_grade
  python manage.py setup_quiz_generate
  python manage.py setup_assignment_generate
  python manage.py setup_studio_ai
fi

# Two ASGI worker processes. Each has its own sync thread, so one stuck
# request cannot block login and the rest of the API. WEB_CONCURRENCY overrides
# the count. Gunicorn recycles a worker whose event loop stops heartbeating.
WORKERS="${WEB_CONCURRENCY:-2}"
echo "✅ Starting Gunicorn with ${WORKERS} Uvicorn workers..."
exec gunicorn backend.asgi:application \
  --worker-class backend.uvicorn_worker.CloudRunUvicornWorker \
  --workers "${WORKERS}" \
  --bind "0.0.0.0:${PORT}" \
  --timeout 120 \
  --graceful-timeout 30 \
  --worker-tmp-dir /dev/shm \
  --keep-alive 65 \
  --forwarded-allow-ips="*" \
  --access-logfile - \
  --error-logfile - \
  --log-level info
