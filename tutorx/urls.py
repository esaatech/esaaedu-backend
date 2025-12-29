"""
URL configuration for tutorx app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Create router for viewset-based views (if needed)
router = DefaultRouter()

urlpatterns = [
    # Add tutorx API endpoints here
    # path('blocks/', views.BlockListView.as_view(), name='block-list'),
    # path('blocks/<uuid:pk>/actions/', views.BlockActionView.as_view(), name='block-actions'),
]

# Include router URLs if using viewsets
urlpatterns += router.urls

