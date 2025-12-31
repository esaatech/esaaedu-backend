"""
TutorX views for block actions and CRUD operations
"""
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db import transaction
import logging

from .models import TutorXBlock
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
from courses.models import Lesson

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


class TutorXBlockListView(APIView):
    """
    GET: List all blocks for a lesson
    PUT: Bulk update blocks (create/update/delete)
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, lesson_id):
        """Get all blocks for a lesson"""
        lesson = get_object_or_404(Lesson, id=lesson_id)
        
        # Check permission - only course teacher can access
        if lesson.course.teacher != request.user:
            return Response(
                {'error': 'Only the course teacher can access this lesson'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verify lesson type is tutorx
        if lesson.type != 'tutorx':
            return Response(
                {'error': 'This lesson is not a TutorX lesson'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        blocks = TutorXBlock.objects.filter(lesson=lesson).order_by('order')
        blocks_data = []
        for block in blocks:
            blocks_data.append({
                'id': str(block.id),
                'block_type': block.block_type,
                'content': block.content,
                'order': block.order,
                'metadata': block.metadata,
            })
        
        return Response({'blocks': blocks_data}, status=status.HTTP_200_OK)
    
    @transaction.atomic
    def put(self, request, lesson_id):
        """Bulk update blocks - handles create, update, and delete"""
        lesson = get_object_or_404(Lesson, id=lesson_id)
        
        # Check permission
        if lesson.course.teacher != request.user:
            return Response(
                {'error': 'Only the course teacher can update blocks'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if lesson.type != 'tutorx':
            return Response(
                {'error': 'This lesson is not a TutorX lesson'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        blocks_data = request.data.get('blocks', [])
        if not isinstance(blocks_data, list):
            return Response(
                {'error': 'blocks must be a list'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get existing blocks - index by both ID and order
        existing_blocks_by_id = {str(block.id): block for block in TutorXBlock.objects.filter(lesson=lesson)}
        existing_blocks_by_order = {block.order: block for block in TutorXBlock.objects.filter(lesson=lesson)}
        incoming_block_ids = set()
        
        # First pass: Temporarily move blocks that will have order conflicts
        # This prevents unique constraint violations when updating orders
        max_order = max([b.get('order', 0) for b in blocks_data] + [0])
        temp_order_start = max_order + 1000  # Use high numbers to avoid conflicts
        
        for block_data in blocks_data:
            block_id = block_data.get('id')
            new_order = block_data.get('order')
            
            if not block_id or not new_order:
                continue
                
            # If this block exists and wants to move to an order occupied by a different block
            if block_id in existing_blocks_by_id:
                existing_block = existing_blocks_by_id[block_id]
                if new_order in existing_blocks_by_order:
                    conflicting_block = existing_blocks_by_order[new_order]
                    # If the block at this order is different from the one we're updating
                    if str(conflicting_block.id) != block_id:
                        # Temporarily move the conflicting block to a high order
                        temp_order = temp_order_start + len([b for b in existing_blocks_by_order.values() if b.order >= temp_order_start])
                        conflicting_block.order = temp_order
                        conflicting_block.save()
                        # Update mappings
                        del existing_blocks_by_order[new_order]
                        existing_blocks_by_order[temp_order] = conflicting_block
        
        # Refresh order mapping after temporary moves
        existing_blocks_by_order = {block.order: block for block in TutorXBlock.objects.filter(lesson=lesson)}
        
        # Second pass: Process all blocks (update by ID, create new, or update by order)
        for block_data in blocks_data:
            block_id = block_data.get('id')
            block_type = block_data.get('block_type')
            content = block_data.get('content', '')
            order = block_data.get('order')
            metadata = block_data.get('metadata', {})
            
            if not block_type or not order:
                continue
            
            block_to_update = None
            
            # Try to match by ID first (this handles most cases including order changes)
            if block_id and block_id in existing_blocks_by_id:
                block_to_update = existing_blocks_by_id[block_id]
            # If not matched by ID, try to match by order (for blocks without IDs)
            elif order in existing_blocks_by_order:
                block_to_update = existing_blocks_by_order[order]
            
            if block_to_update:
                # Update existing block
                block_to_update.block_type = block_type
                block_to_update.content = content
                block_to_update.order = order
                block_to_update.metadata = metadata
                block_to_update.save()
                incoming_block_ids.add(str(block_to_update.id))
            else:
                # Create new block (no existing block at this order)
                new_block = TutorXBlock.objects.create(
                    lesson=lesson,
                    block_type=block_type,
                    content=content,
                    order=order,
                    metadata=metadata
                )
                incoming_block_ids.add(str(new_block.id))
        
        # Delete blocks not in the request
        blocks_to_delete = set(existing_blocks_by_id.keys()) - incoming_block_ids
        if blocks_to_delete:
            TutorXBlock.objects.filter(
                lesson=lesson,
                id__in=blocks_to_delete
            ).delete()
        
        # Return updated blocks
        blocks = TutorXBlock.objects.filter(lesson=lesson).order_by('order')
        blocks_data = []
        for block in blocks:
            blocks_data.append({
                'id': str(block.id),
                'block_type': block.block_type,
                'content': block.content,
                'order': block.order,
                'metadata': block.metadata,
            })
        
        return Response({'blocks': blocks_data}, status=status.HTTP_200_OK)


class TutorXBlockDetailView(APIView):
    """
    GET: Get a specific block
    PUT: Update a block
    DELETE: Delete a block
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, block_id):
        """Get a specific block"""
        block = get_object_or_404(TutorXBlock, id=block_id)
        
        # Check permission
        if block.lesson.course.teacher != request.user:
            return Response(
                {'error': 'Only the course teacher can access this block'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return Response({
            'id': str(block.id),
            'block_type': block.block_type,
            'content': block.content,
            'order': block.order,
            'metadata': block.metadata,
        }, status=status.HTTP_200_OK)
    
    def put(self, request, block_id):
        """Update a block"""
        block = get_object_or_404(TutorXBlock, id=block_id)
        
        # Check permission
        if block.lesson.course.teacher != request.user:
            return Response(
                {'error': 'Only the course teacher can update blocks'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        block_type = request.data.get('block_type')
        content = request.data.get('content')
        order = request.data.get('order')
        metadata = request.data.get('metadata')
        
        if block_type:
            block.block_type = block_type
        if content is not None:
            block.content = content
        if order is not None:
            block.order = order
        if metadata is not None:
            block.metadata = metadata
        
        try:
            block.save()
            return Response({
                'id': str(block.id),
                'block_type': block.block_type,
                'content': block.content,
                'order': block.order,
                'metadata': block.metadata,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error updating block: {e}")
            return Response(
                {'error': 'Failed to update block', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request, block_id):
        """Delete a block"""
        block = get_object_or_404(TutorXBlock, id=block_id)
        
        # Check permission
        if block.lesson.course.teacher != request.user:
            return Response(
                {'error': 'Only the course teacher can delete blocks'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            block.delete()
            return Response(
                {'message': 'Block deleted successfully'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error deleting block: {e}")
            return Response(
                {'error': 'Failed to delete block', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
