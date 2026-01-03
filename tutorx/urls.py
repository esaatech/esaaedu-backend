"""
URL configuration for tutorx app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for viewset-based views (if needed)
router = DefaultRouter()

urlpatterns = [
    # Block CRUD operations (must come before action routes to avoid conflicts)
    path('lessons/<uuid:lesson_id>/blocks/', views.TutorXBlockListView.as_view(), name='tutorx-block-list'),
    path('blocks/', views.TutorXBlockCreateView.as_view(), name='tutorx-block-create'),  # POST to create
    path('blocks/<uuid:block_id>/', views.TutorXBlockDetailView.as_view(), name='tutorx-block-detail'),  # GET, PUT, DELETE
    
    # Block actions - perform AI actions on blocks (must come after blocks/ to avoid conflicts)
    path('blocks/<str:action_type>/', views.BlockActionView.as_view(), name='block-action'),
    
    # Image operations
    path('images/upload/', views.TutorXImageUploadView.as_view(), name='tutorx-image-upload'),
    path('images/delete/', views.TutorXImageDeleteView.as_view(), name='tutorx-image-delete'),
]

# Include router URLs if using viewsets
urlpatterns += router.urls

