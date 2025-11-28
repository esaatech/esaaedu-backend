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
    path('courses/<uuid:course_id>/ai/generate-course-detail/', views.AIGenerateCourseDetailView.as_view(), name='ai_generate_course_detail'),
    path('courses/<uuid:course_id>/ai/generate-lessons/', views.AIGenerateCourseLessonsView.as_view(), name='ai_generate_course_lessons'),
    path('lessons/<uuid:lesson_id>/ai/generate-quiz/', views.AIGenerateQuizView.as_view(), name='ai_generate_quiz'),
    path('lessons/<uuid:lesson_id>/ai/generate-assignment/', views.AIGenerateAssignmentView.as_view(), name='ai_generate_assignment'),
    
    # Video Material URLs
    path('video-materials/', views.VideoMaterialView.as_view(), name='video_material_create'),
    path('video-materials/<uuid:video_material_id>/', views.VideoMaterialView.as_view(), name='video_material_detail'),
    path('video-materials/<uuid:video_material_id>/transcribe/', views.VideoMaterialTranscribeView.as_view(), name='video_material_transcribe'),
    
    # Document Upload URLs
    path('documents/upload/', views.DocumentUploadView.as_view(), name='document_upload'),
    
    # Audio/Video Upload URLs
    path('audio-video/upload/', views.AudioVideoUploadView.as_view(), name='audio_video_upload'),
    
    # Messaging URLs
    path('students/<int:student_id>/conversations/', views.StudentConversationsListView.as_view(), name='student_conversations'),
    path('conversations/<uuid:conversation_id>/messages/', views.ConversationMessagesView.as_view(), name='conversation_messages'),
    path('messages/<uuid:message_id>/read/', views.MarkMessageReadView.as_view(), name='mark_message_read'),
    path('conversations/unread-count/', views.UnreadCountView.as_view(), name='unread_count'),
    path('students/<int:student_id>/unread-count/', views.StudentUnreadCountView.as_view(), name='student_unread_count'),
]
