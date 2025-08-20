from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    # Public endpoints (for students/frontend)
    path('featured/', views.featured_courses, name='featured_courses'),
    path('public/', views.public_courses_list, name='public_courses_list'),
    
    # Teacher endpoints
    path('teacher/', views.teacher_courses, name='teacher_courses'),
]
