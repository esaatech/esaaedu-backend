from django.urls import path
from . import views

app_name = 'teacher'

urlpatterns = [
    path('profile/', views.TeacherProfileAPIView.as_view(), name='teacher_profile'),
]
