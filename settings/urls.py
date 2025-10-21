from django.urls import path
from . import views

app_name = 'settings'

urlpatterns = [
    # Dashboard settings management
    path('dashboard-settings/', views.UserDashboardSettingsView.as_view(), name='dashboard-settings'),
    path('dashboard-config/', views.get_dashboard_config, name='dashboard-config'),
    path('reset-defaults/', views.reset_to_defaults, name='reset-defaults'),
    
    # Teacher-specific settings management
    path('teacher-dashboard-settings/', views.TeacherDashboardSettingsView.as_view(), name='teacher-dashboard-settings'),
    path('teacher-config/', views.get_teacher_config, name='teacher-config'),
]
