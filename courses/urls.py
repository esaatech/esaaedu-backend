from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    # Public endpoints (for students/frontend)
    path('featured/', views.featured_courses, name='featured_courses'),
    path('public/', views.public_courses_list, name='public_courses_list'),
    path('public/<uuid:course_id>/introduction/', views.course_introduction_detail, name='course_introduction_detail'),
    
    # Teacher endpoints
    path('teacher/', views.teacher_courses, name='teacher_courses'),
    path('teacher/<uuid:course_id>/', views.teacher_course_detail, name='teacher_course_detail'),
    
    # Lesson management endpoints
    path('<uuid:course_id>/lessons/', views.course_lessons, name='course_lessons'),
    path('lessons/<uuid:lesson_id>/', views.lesson_detail, name='lesson_detail'),
    path('lessons/<uuid:lesson_id>/complete/', views.complete_lesson, name='complete_lesson'),
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
    
    # Class management endpoints
    path('teacher/classes/', views.teacher_classes, name='teacher_classes'),
    path('teacher/classes/<uuid:class_id>/', views.teacher_class_detail, name='teacher_class_detail'),
    path('teacher/courses/<uuid:course_id>/students/', views.course_enrolled_students, name='course_enrolled_students'),
    
    # Teacher student management
    path('teacher/students/', views.teacher_students, name='teacher_students'),
    
    # Class event endpoints
    path('teacher/classes/<uuid:class_id>/events/', views.class_events, name='class_events'),
    path('teacher/classes/<uuid:class_id>/events/<uuid:event_id>/', views.class_event_detail, name='class_event_detail'),
    
    # Quiz grading endpoints
    path('teacher/quiz-submissions/', views.teacher_quiz_submissions, name='teacher_quiz_submissions'),
    path('teacher/quiz-attempts/<uuid:attempt_id>/', views.quiz_attempt_details, name='quiz_attempt_details'),
    path('teacher/quiz-attempts/<uuid:attempt_id>/grade/', views.save_quiz_grade, name='save_quiz_grade'),
    
    # Student enrollment endpoints
    path('student/enrolled/', views.student_enrolled_courses, name='student_enrolled_courses'),
    path('student/recommendations/', views.student_course_recommendations, name='student_course_recommendations'),
    path('student/enroll/<uuid:course_id>/', views.student_enroll_course, name='student_enroll_course'),
    path('student/courses/<uuid:course_id>/lessons/', views.student_course_lessons, name='student_course_lessons'),
    path('student/lessons/<uuid:lesson_id>/', views.student_lesson_detail, name='student_lesson_detail'),
    path('student/lessons/<uuid:lesson_id>/quiz/', views.student_lesson_quiz, name='student_lesson_quiz'),
    path('student/lessons/<uuid:lesson_id>/quiz/submit/', views.submit_quiz_attempt, name='submit_quiz_attempt'),
    
    # Course classes endpoint (for enrollment)
    path('<uuid:course_id>/classes/', views.course_available_classes, name='course_available_classes'),
]
