from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.http import Http404
import logging
from .models import AIPromptTemplate

logger = logging.getLogger(__name__)


class AIPromptTemplateView(APIView):
    """
    API endpoint to fetch AI Prompt Template by name.
    
    GET: Retrieve prompt template by name
    Endpoint: GET /api/ai/prompt-templates/{name}/
    
    Response:
    {
        "name": "course_detail",
        "display_name": "Course Detail Generation",
        "description": "...",
        "default_system_instruction": "...",
        "model_name": "gemini-2.0-flash-001",
        "temperature": 0.7,
        "max_tokens": null,
        "is_active": true
    }
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, name):
        """
        GET: Retrieve prompt template by name.
        """
        try:
            template = AIPromptTemplate.objects.filter(
                name=name,
                is_active=True
            ).first()
            
            if not template:
                return Response(
                    {'error': f'Prompt template "{name}" not found or is inactive'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            return Response({
                'name': template.name,
                'display_name': template.display_name,
                'description': template.description,
                'default_system_instruction': template.default_system_instruction,
                'model_name': template.model_name,
                'temperature': template.temperature,
                'max_tokens': template.max_tokens,
                'is_active': template.is_active
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching AI prompt template '{name}': {e}", exc_info=True)
            return Response(
                {'error': f'Error fetching prompt template: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
