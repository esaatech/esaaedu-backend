from django.urls import path
from . import views

app_name = 'teacher'

urlpatterns = [
    path('profile/', views.TeacherProfileAPIView.as_view(), name='teacher_profile'),
    path('schedule/', views.TeacherScheduleAPIView.as_view(), name='teacher_schedule'),
    
    # Project Management URLs
    path('projects/', views.ProjectManagementView.as_view(), name='project_management'),
    path('projects/<int:project_id>/', views.ProjectManagementView.as_view(), name='project_detail'),
    path('projects/<int:project_id>/grading/', views.ProjectGradingView.as_view(), name='project_grading'),
    path('projects/submissions/<int:submission_id>/', views.ProjectSubmissionDetailView.as_view(), name='submission_detail'),
    path('projects/dashboard/', views.ProjectDashboardView.as_view(), name='project_dashboard'),
    
    # Assignment Management URLs
    path('assignments/', views.AssignmentManagementView.as_view(), name='assignment_management'),
    path('assignments/<uuid:assignment_id>/', views.AssignmentManagementView.as_view(), name='assignment_detail'),
    path('assignments/<uuid:assignment_id>/questions/', views.AssignmentQuestionManagementView.as_view(), name='assignment_questions'),
    path('assignments/<uuid:assignment_id>/questions/<uuid:question_id>/', views.AssignmentQuestionManagementView.as_view(), name='assignment_question_detail'),
    path('assignments/<uuid:assignment_id>/grading/', views.AssignmentGradingView.as_view(), name='assignment_grading'),
    path('assignments/<uuid:assignment_id>/grading/<uuid:submission_id>/', views.AssignmentGradingView.as_view(), name='assignment_submission_grading'),
    path('assignments/<uuid:assignment_id>/grading/<uuid:submission_id>/ai-grade/', views.AssignmentAIGradingView.as_view(), name='assignment_ai_grading'),
    
    # AI Generation URLs
    path('courses/<uuid:course_id>/ai/generate-introduction/', views.AIGenerateCourseIntroductionView.as_view(), name='ai_generate_course_introduction'),
    path('courses/<uuid:course_id>/ai/generate-lessons/', views.AIGenerateCourseLessonsView.as_view(), name='ai_generate_course_lessons'),
    path('lessons/<uuid:lesson_id>/ai/generate-quiz/', views.AIGenerateQuizView.as_view(), name='ai_generate_quiz'),
    path('lessons/<uuid:lesson_id>/ai/generate-assignment/', views.AIGenerateAssignmentView.as_view(), name='ai_generate_assignment'),
    
    # Video Material URLs
    path('video-materials/', views.VideoMaterialView.as_view(), name='video_material_create'),
    path('video-materials/<uuid:video_material_id>/', views.VideoMaterialView.as_view(), name='video_material_detail'),
    path('video-materials/<uuid:video_material_id>/transcribe/', views.VideoMaterialTranscribeView.as_view(), name='video_material_transcribe'),
    
    # Document Upload URLs
    path('documents/upload/', views.DocumentUploadView.as_view(), name='document_upload'),
]
