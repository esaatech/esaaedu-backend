# Little Learners Tech - Backend

Django REST API backend for the Little Learners Tech educational platform.

## Features

- Django REST Framework for API endpoints
- Firebase Authentication integration
- PostgreSQL database support
- User management (Teachers and Students)
- Course and lesson management
- Quiz system with progress tracking

## Setup

1. Install dependencies:
   ```bash
   poetry install
   ```

2. Set up environment variables in `.env` file

3. Run migrations:
   ```bash
   poetry run python manage.py migrate
   ```

4. Start development server:
   ```bash
   poetry run python manage.py runserver
   ```

## API Endpoints

- `/api/auth/` - Authentication endpoints
- `/api/teacher/` - Teacher-specific endpoints
- `/api/student/` - Student-specific endpoints
- `/api/courses/` - Course management
- `/api/lessons/` - Lesson content
- `/api/quizzes/` - Quiz system

## Documentation

- [CSS File Upload to Google Cloud Storage](student/docs/CSS_FILE_UPLOAD.md) - Documentation for the CSS file upload system, including URL consistency, caching prevention, and GCS integration
