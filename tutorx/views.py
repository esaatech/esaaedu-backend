"""
TutorX views for block actions
"""
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
import logging

from .services.ai import TutorXAIService
from .serializers import (
    BlockActionRequestSerializer,
    ExplainMoreResponseSerializer,
    GiveExamplesResponseSerializer,
    SimplifyResponseSerializer,
    SummarizeResponseSerializer,
    GenerateQuestionsResponseSerializer,
)
from settings.models import UserTutorXInstruction

logger = logging.getLogger(__name__)


class BlockActionView(APIView):
    """
    API View for performing AI actions on content blocks.
    
    Handles actions like explain_more, give_examples, simplify, summarize, generate_questions.
    Also manages user instruction loading and saving.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, action_type):
        """
        POST: Perform an AI action on a block.
        
        Expected payload:
        {
            "block_content": "...",
            "block_type": "text",
            "context": {...},
            "user_prompt": "...",  # Optional, if not provided uses default
            "user_prompt_changed": false,  # If true, saves user_prompt to UserTutorXInstruction
            "temperature": 0.7,
            "max_tokens": null,
            ...action-specific params
        }
        """
        action_type = action_type.lower()
        valid_actions = ['explain_more', 'give_examples', 'simplify', 'summarize', 'generate_questions']
        
        if action_type not in valid_actions:
            return Response(
                {'error': f'Invalid action type. Must be one of: {", ".join(valid_actions)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate request data
        serializer = BlockActionRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        
        # Get user prompt - either from request or load from UserTutorXInstruction
        user_prompt = validated_data.get('user_prompt')
        user_prompt_changed = validated_data.get('user_prompt_changed', False)
        
        # If user_prompt not provided, load from UserTutorXInstruction
        if not user_prompt:
            try:
                user_instruction = UserTutorXInstruction.get_or_create_settings(
                    user=request.user,
                    action_type=action_type
                )
                user_prompt = user_instruction.user_instruction
            except Exception as e:
                logger.warning(f"Failed to load user instruction: {e}")
                # Fallback to default from service
                pass
        
        # If user customized the prompt, save it
        if user_prompt_changed and user_prompt:
            try:
                user_instruction = UserTutorXInstruction.get_or_create_settings(
                    user=request.user,
                    action_type=action_type
                )
                user_instruction.user_instruction = user_prompt
                user_instruction.save()
            except Exception as e:
                # Log error but don't fail the request
                logger.error(f"Failed to save user instruction: {e}", exc_info=True)
        
        # Prepare service call parameters
        service_params = {
            'block_content': validated_data['block_content'],
            'block_type': validated_data.get('block_type', 'text'),
            'context': validated_data.get('context'),
            'user_prompt': user_prompt,
            'temperature': validated_data.get('temperature', 0.7),
        }
        
        if validated_data.get('max_tokens'):
            service_params['max_tokens'] = validated_data['max_tokens']
        
        # Add action-specific parameters
        if action_type == 'give_examples':
            service_params['num_examples'] = validated_data.get('num_examples', 3)
            service_params['example_type'] = validated_data.get('example_type', 'practical')
        elif action_type == 'simplify':
            service_params['target_level'] = validated_data.get('target_level', 'beginner')
        elif action_type == 'summarize':
            service_params['length'] = validated_data.get('length', 'brief')
        elif action_type == 'generate_questions':
            service_params['num_questions'] = validated_data.get('num_questions', 3)
            service_params['question_types'] = validated_data.get('question_types')
        
        # Call the AI service
        try:
            service = TutorXAIService()
            method = getattr(service, action_type)
            result = method(**service_params)
            
            # Validate and serialize response based on action type
            response_serializers = {
                'explain_more': ExplainMoreResponseSerializer,
                'give_examples': GiveExamplesResponseSerializer,
                'simplify': SimplifyResponseSerializer,
                'summarize': SummarizeResponseSerializer,
                'generate_questions': GenerateQuestionsResponseSerializer,
            }
            
            response_serializer = response_serializers[action_type](data=result)
            if response_serializer.is_valid():
                return Response(response_serializer.validated_data, status=status.HTTP_200_OK)
            else:
                # If validation fails, return raw result (shouldn't happen, but be safe)
                logger.warning(f"Response validation failed for {action_type}: {response_serializer.errors}")
                return Response(result, status=status.HTTP_200_OK)
                
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error in {action_type}: {e}", exc_info=True)
            return Response(
                {'error': f'Failed to process {action_type} action', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
