from django.urls import path
from . import views

app_name = 'ai'

urlpatterns = [
    path('prompt-templates/<str:name>/', views.AIPromptTemplateView.as_view(), name='ai_prompt_template'),
]
