from django.urls import path
from . import views

app_name = 'authentication'

urlpatterns = [
    # Token verification
    path('verify-token/', views.verify_token, name='verify_token'),
    
    # Student-focused endpoints
    path('student/signup/', views.student_signup, name='student_signup'),
    path('student/login/', views.student_login, name='student_login'),
    
    # Teacher-focused endpoints
    path('teacher/signup/', views.teacher_signup, name='teacher_signup'),
    path('teacher/login/', views.teacher_login, name='teacher_login'),
    
    # User profile endpoints
    path('user/', views.AuthenticatedUserView.as_view(), name='current_user'),
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),
    path('complete-setup/', views.complete_profile_setup, name='complete_setup'),
    
    # Admin endpoints
    path('users/<int:user_id>/role/', views.UpdateUserRoleView.as_view(), name='update_user_role'),
]
