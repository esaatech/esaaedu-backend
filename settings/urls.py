from django.urls import path
from . import views

app_name = 'settings'

urlpatterns = [
    # Dashboard settings management
    path('dashboard-settings/', views.UserDashboardSettingsView.as_view(), name='dashboard-settings'),
    path('dashboard-config/', views.get_dashboard_config, name='dashboard-config'),
    path('reset-defaults/', views.reset_to_defaults, name='reset-defaults'),
]
