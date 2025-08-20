from django.urls import path
from . import views

app_name = 'authentication'

urlpatterns = [
    # Token verification
    path('verify-token/', views.verify_token, name='verify_token'),
    
    # User profile endpoints
    path('user/', views.AuthenticatedUserView.as_view(), name='current_user'),
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),
    path('complete-setup/', views.complete_profile_setup, name='complete_setup'),
    
    # Admin endpoints
    path('users/<int:user_id>/role/', views.UpdateUserRoleView.as_view(), name='update_user_role'),
]
