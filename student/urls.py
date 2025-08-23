from django.urls import path
from . import views

urlpatterns = [
    # Enrolled Courses
    path('enrolled-courses/', views.enrolled_courses, name='enrolled_courses'),
    path('enrolled-courses/<uuid:enrollment_id>/', views.enrolled_course_detail, name='enrolled_course_detail'),
    
    # TODO: Add other student-related endpoints as needed
    # path('attendance/', views.student_attendance, name='student_attendance'),
    # path('attendance/<uuid:attendance_id>/', views.student_attendance_detail, name='student_attendance_detail'),
    # path('grades/', views.student_grades, name='student_grades'),
    # path('grades/<uuid:grade_id>/', views.student_grade_detail, name='student_grade_detail'),
    # path('behavior/', views.student_behavior, name='student_behavior'),
    # path('notes/', views.student_notes, name='student_notes'),
    # path('communications/', views.student_communications, name='student_communications'),
]
