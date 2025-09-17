from django.urls import path
from . import views

urlpatterns = [
    # Enrolled Courses
    path('enrolled-courses/', views.enrolled_courses, name='enrolled_courses'),
    path('enrolled-courses/<uuid:enrollment_id>/', views.enrolled_course_detail, name='enrolled_course_detail'),
    
    # Assessments
    path('enrolled-courses/<uuid:enrollment_id>/lesson-assessments/', views.lesson_assessments, name='lesson_assessments'),
    path('enrolled-courses/<uuid:enrollment_id>/teacher-assessments/', views.teacher_assessments, name='teacher_assessments'),
    path('students/<int:student_id>/assessments-overview/', views.student_assessments_overview, name='student_assessments_overview'),
    path('assessments/create-lesson/', views.create_lesson_assessment_direct, name='create_lesson_assessment_direct'),
    path('assessments/create-teacher/', views.create_teacher_assessment_direct, name='create_teacher_assessment_direct'),
    path('assessments/update-teacher/<uuid:assessment_id>/', views.update_teacher_assessment, name='update_teacher_assessment'),
    path('assessments/update-lesson/<uuid:assessment_id>/', views.update_lesson_assessment, name='update_lesson_assessment'),
    
    # New consolidated endpoint
    path('teacher-student-record/<int:student_id>/', views.TeacherStudentRecord.as_view(), name='teacher_student_record'),
    
    # Schedule
    path('schedule/', views.StudentScheduleView.as_view(), name='student_schedule'),
    
    # Dashboard Overview
    path('dashboard-overview/', views.DashboardOverview.as_view(), name='dashboard_overview'),
    
    # Dashboard Assessment endpoints - SPECIFIC PATTERNS FIRST
    path('dashboard-assessments/quiz/<uuid:quiz_attempt_id>/', views.QuizDetailView.as_view(), name='quiz_detail'),
    path('dashboard-assessments/teacher/<uuid:course_id>/<uuid:teacher_id>/', views.TeacherAssessmentListView.as_view(), name='teacher_assessment_list'),
    path('dashboard-assessments/teacher/<uuid:assessment_id>/detail/', views.TeacherAssessmentDetailView.as_view(), name='teacher_assessment_detail'),

    # Dashboard Assessment overview - GENERAL PATTERN LAST
    path('dashboard-assessments/', views.DashboardAssessmentView.as_view(), name='dashboard_assessments'),
    
    # Assessment View - Single endpoint for all assessment data
    path('assessments/', views.AssessmentView.as_view(), name='assessments'),
    
    # Feedback System
    path('feedback/question/<uuid:quiz_attempt_id>/<uuid:question_id>/', views.quiz_question_feedback, name='quiz_question_feedback'),
    path('feedback/attempt/<uuid:quiz_attempt_id>/', views.quiz_attempt_feedback, name='quiz_attempt_feedback'),
    path('feedback/overview/<int:student_id>/', views.student_feedback_overview, name='student_feedback_overview'),
    
    # TODO: Add other student-related endpoints as needed
    # path('attendance/', views.student_attendance, name='student_attendance'),
    # path('attendance/<uuid:attendance_id>/', views.student_attendance_detail, name='student_attendance_detail'),
    # path('grades/', views.student_grades, name='student_grades'),
    # path('grades/<uuid:grade_id>/', views.student_grade_detail, name='student_grade_detail'),
    # path('behavior/', views.student_behavior, name='student_behavior'),
    # path('notes/', views.student_notes, name='student_notes'),
    # path('communications/', views.student_communications, name='student_communications'),
]
