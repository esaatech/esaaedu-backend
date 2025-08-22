from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    # Public endpoints (for students/frontend)
    path('featured/', views.featured_courses, name='featured_courses'),
    path('public/', views.public_courses_list, name='public_courses_list'),
    
    # Teacher endpoints
    path('teacher/', views.teacher_courses, name='teacher_courses'),
    path('teacher/<uuid:course_id>/', views.teacher_course_detail, name='teacher_course_detail'),
    
    # Lesson management endpoints
    path('<uuid:course_id>/lessons/', views.course_lessons, name='course_lessons'),
    path('lessons/<uuid:lesson_id>/', views.lesson_detail, name='lesson_detail'),
    path('<uuid:course_id>/lessons/reorder/', views.reorder_lessons, name='reorder_lessons'),
    
    # Quiz management endpoints
    path('lessons/<uuid:lesson_id>/quiz/', views.lesson_quiz, name='lesson_quiz'),
    path('quizzes/<uuid:quiz_id>/', views.quiz_detail, name='quiz_detail'),
    path('quizzes/<uuid:quiz_id>/questions/', views.quiz_questions, name='quiz_questions'),
    path('questions/<uuid:question_id>/', views.question_detail, name='question_detail'),
    
    # Course introduction endpoint
    path('teacher/<uuid:course_id>/introduction/', views.course_introduction, name='course_introduction'),
    
    # Notes management endpoints (lesson-specific)
    path('lessons/<uuid:lesson_id>/notes/', views.lesson_notes, name='lesson_notes'),
    path('lessons/<uuid:lesson_id>/notes/<uuid:note_id>/', views.lesson_note_detail, name='lesson_note_detail'),
]
