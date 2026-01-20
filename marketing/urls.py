from django.urls import path
from . import views

app_name = 'marketing'

urlpatterns = [
    path('<slug:slug>/', views.ProgramBySlugView.as_view(), name='program_by_slug'),
]

