"""
URL configuration for tutorx app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for viewset-based views (if needed)
router = DefaultRouter()

urlpatterns = [
    # Block actions - perform AI actions on blocks
    path('blocks/<str:action_type>/', views.BlockActionView.as_view(), name='block-action'),
]

# Include router URLs if using viewsets
urlpatterns += router.urls

