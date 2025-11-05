# Use Python 3.11 slim image
FROM python:3.11-slim



# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml poetry.lock ./
RUN pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install --only=main --no-interaction --no-ansi

# Copy project
COPY . .

# Make entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Create staticfiles directory and collect static files
RUN mkdir -p /app/staticfiles
RUN python manage.py collectstatic --noinput --clear

# Note: Database migrations are NOT run during build
# They should be run:
# 1. At container startup (via entrypoint script), OR
# 2. Via Cloud Build step before deploying, OR  
# 3. Via Cloud Run init container
# This is because migrations require database connection which isn't available during build



# Expose port
EXPOSE 8080

# Add health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:$PORT/ || exit 1

# Use entrypoint script to run migrations before starting server
ENTRYPOINT ["/app/entrypoint.sh"]
