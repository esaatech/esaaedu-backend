from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
from django.http import Http404
from .models import Program
from .serializers import ProgramSerializer
import logging

logger = logging.getLogger(__name__)


class ProgramBySlugView(APIView):
    """
    Public API endpoint to fetch Program details by slug.
    Returns program information with all associated courses,
    including full enrollment data (billing, classes, etc.).
    
    URL: /api/marketing/programs/<slug>/
    Method: GET
    Authentication: None (public endpoint)
    """
    permission_classes = [AllowAny]
    
    def get(self, request, slug):
        """
        Get program by slug with enriched courses data.
        
        Returns:
        - 200: Program data with courses array
        - 404: Program not found or inactive
        - 500: Server error
        """
        try:
            # Get program by slug (must be active)
            program = get_object_or_404(Program, slug=slug, is_active=True)
            
            # Serialize program with courses
            # The serializer will:
            # 1. Get courses using program.get_courses() (converts category to courses if needed)
            # 2. Enrich each course with full details, billing, and classes
            serializer = ProgramSerializer(program, context={'request': request})
            
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Http404:
            # get_object_or_404 raises Http404 if not found
            return Response(
                {
                    'error': 'Program not found',
                    'details': f"No active program found with slug '{slug}'"
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error fetching program by slug '{slug}': {e}", exc_info=True)
            return Response(
                {
                    'error': 'Failed to fetch program',
                    'details': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

