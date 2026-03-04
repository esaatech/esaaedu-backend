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
- `/api/blog/` - Blog (list and detail by slug; see [Blog API](docs/blog-api.md))
- `/api/lead-magnet/<slug>/` - Lead magnet guide (public); see [Lead Magnet docs](lead_magnet/docs/README.md)

## Documentation

- [Assignment return and feedback](courses/docs/assignment_return_and_feedback.md) - Return submission to student as draft, `return_feedback`, `return_for_revision_count`, and `graded_questions`; how student lesson exposes per-question feedback
- [TutorX assignment submission](tutorx/ASSIGNMENT_SUBMISSION.md) - Autograde and return-for-revision flow for TutorX lessons; max returns and `return_for_revision_count`
- [Blog API](blog/docs/blog-api.md) - Public blog API: list posts and get post by slug; posts managed in Django Admin
- [Lead Magnet](lead_magnet/docs/README.md) - Lead magnet API, admin, GCP storage, and Brevo integration
- [CSS File Upload to Google Cloud Storage](student/docs/CSS_FILE_UPLOAD.md) - Documentation for the CSS file upload system, including URL consistency, caching prevention, and GCS integration
