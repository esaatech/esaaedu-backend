"""
TutorX views for block actions and CRUD operations
"""
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import F
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
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from PIL import Image as PILImage
from io import BytesIO
import uuid
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from PIL import Image
from io import BytesIO
import uuid

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
        
        # Verify lesson type is tutorx
        if lesson.type != 'tutorx':
            return Response(
                {'error': 'This lesson is not a TutorX lesson'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check permission - allow course teacher OR enrolled students
        is_teacher = lesson.course.teacher == request.user
        is_student = False
        
        # Check if user is an enrolled student
        if not is_teacher and hasattr(request.user, 'student_profile'):
            from student.models import EnrolledCourse
            is_student = EnrolledCourse.objects.filter(
                student_profile=request.user.student_profile,
                course=lesson.course,
                status__in=['active', 'completed']
            ).exists()
        
        if not is_teacher and not is_student:
            return Response(
                {'error': 'Only the course teacher or enrolled students can access this lesson'},
                status=status.HTTP_403_FORBIDDEN
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
        
        # Delete blocks not in the request and cleanup their images from GCS
        blocks_to_delete = set(existing_blocks_by_id.keys()) - incoming_block_ids
        if blocks_to_delete:
            blocks_to_delete_objs = TutorXBlock.objects.filter(
                lesson=lesson,
                id__in=blocks_to_delete
            )
            
            # Delete images from GCS before deleting blocks
            for block in blocks_to_delete_objs:
                if block.block_type == 'image' and block.content:
                    try:
                        # Extract file path from GCS URL
                        from urllib.parse import urlparse, unquote
                        parsed_url = urlparse(block.content)
                        path_parts = parsed_url.path.strip('/').split('/', 1)
                        if len(path_parts) > 1:
                            file_path = unquote(path_parts[1])
                        else:
                            file_path = unquote(parsed_url.path.strip('/'))
                        
                        if default_storage.exists(file_path):
                            default_storage.delete(file_path)
                            logger.info(f"✅ Deleted image from GCS when deleting block: {file_path}")
                    except Exception as e:
                        logger.error(f"❌ Failed to delete image from GCS when deleting block: {e}")
            
            # Now delete the blocks
            blocks_to_delete_objs.delete()
        
        # Handle image replacement: if an image block's URL changed, delete old image
        for block_data in blocks_data:
            if block_data.get('block_type') == 'image':
                block_id = block_data.get('id')
                new_image_url = block_data.get('content', '') or block_data.get('metadata', {}).get('image_url', '')
                
                if block_id and block_id in existing_blocks_by_id:
                    old_block = existing_blocks_by_id[block_id]
                    old_image_url = old_block.content or old_block.metadata.get('image_url', '')
                    
                    # If image URL changed, delete old image from GCS
                    if old_image_url and old_image_url != new_image_url:
                        try:
                            from urllib.parse import urlparse, unquote
                            parsed_url = urlparse(old_image_url)
                            path_parts = parsed_url.path.strip('/').split('/', 1)
                            if len(path_parts) > 1:
                                file_path = unquote(path_parts[1])
                            else:
                                file_path = unquote(parsed_url.path.strip('/'))
                            
                            if default_storage.exists(file_path):
                                default_storage.delete(file_path)
                                logger.info(f"✅ Deleted old image from GCS when replacing: {file_path}")
                        except Exception as e:
                            logger.error(f"❌ Failed to delete old image from GCS when replacing: {e}")
        
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


class TutorXBlockCreateView(APIView):
    """
    POST: Create a new TutorX block
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        """Create a new block"""
        lesson_id = request.data.get('lesson')
        block_type = request.data.get('block_type')
        content = request.data.get('content', '')
        order = request.data.get('order')
        metadata = request.data.get('metadata', {})
        
        # Validate required fields
        if not lesson_id:
            return Response(
                {'error': 'lesson is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not block_type:
            return Response(
                {'error': 'block_type is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if order is None:
            return Response(
                {'error': 'order is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get lesson
        try:
            lesson = Lesson.objects.get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response(
                {'error': 'Lesson not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permission
        if lesson.course.teacher != request.user:
            return Response(
                {'error': 'Only the course teacher can create blocks'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verify lesson type
        if lesson.type != 'tutorx':
            return Response(
                {'error': 'This lesson is not a TutorX lesson'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Handle order conflicts - shift existing blocks if needed
        existing_block_at_order = TutorXBlock.objects.filter(
            lesson=lesson,
            order=order
        ).first()
        
        if existing_block_at_order:
            # Shift all blocks with order >= new_order by 1
            TutorXBlock.objects.filter(
                lesson=lesson,
                order__gte=order
            ).update(order=F('order') + 1)
            logger.info(f"Shifted blocks for lesson {lesson_id} starting from order {order}")
        
        # Create the new block
        try:
            new_block = TutorXBlock.objects.create(
                lesson=lesson,
                block_type=block_type,
                content=content,
                order=order,
                metadata=metadata
            )
            
            logger.info(f"✅ Created new TutorX block: {new_block.id} (type: {block_type}, order: {order})")
            
            return Response({
                'id': str(new_block.id),
                'lesson': str(new_block.lesson.id),
                'block_type': new_block.block_type,
                'content': new_block.content,
                'order': new_block.order,
                'metadata': new_block.metadata,
                'created_at': new_block.created_at.isoformat(),
                'updated_at': new_block.updated_at.isoformat(),
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating block: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to create block', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
            'lesson': str(block.lesson.id),
            'block_type': block.block_type,
            'content': block.content,
            'order': block.order,
            'metadata': block.metadata,
            'created_at': block.created_at.isoformat(),
            'updated_at': block.updated_at.isoformat(),
        }, status=status.HTTP_200_OK)
    
    @transaction.atomic
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
        
        # Handle order conflicts if order is being changed
        old_order = block.order
        if order is not None and order != old_order:
            # Check if new order is occupied by another block
            existing_block_at_order = TutorXBlock.objects.filter(
                lesson=block.lesson,
                order=order
            ).exclude(id=block.id).first()
            
            if existing_block_at_order:
                # Shift blocks to make room
                if order > old_order:
                    # Moving down - shift blocks between old and new order up
                    TutorXBlock.objects.filter(
                        lesson=block.lesson,
                        order__gt=old_order,
                        order__lte=order
                    ).exclude(id=block.id).update(order=F('order') - 1)
                else:
                    # Moving up - shift blocks between new and old order down
                    TutorXBlock.objects.filter(
                        lesson=block.lesson,
                        order__gte=order,
                        order__lt=old_order
                    ).exclude(id=block.id).update(order=F('order') + 1)
        
        # Update block fields
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
            logger.info(f"✅ Updated TutorX block: {block.id}")
            
            return Response({
                'id': str(block.id),
                'lesson': str(block.lesson.id),
                'block_type': block.block_type,
                'content': block.content,
                'order': block.order,
                'metadata': block.metadata,
                'created_at': block.created_at.isoformat(),
                'updated_at': block.updated_at.isoformat(),
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error updating block: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to update block', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @transaction.atomic
    def delete(self, request, block_id):
        """Delete a block"""
        block = get_object_or_404(TutorXBlock, id=block_id)
        
        # Check permission
        if block.lesson.course.teacher != request.user:
            return Response(
                {'error': 'Only the course teacher can delete blocks'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Delete image from GCS if it's an image block
        if block.block_type == 'image' and block.content:
            try:
                from urllib.parse import urlparse, unquote
                parsed_url = urlparse(block.content)
                path_parts = parsed_url.path.strip('/').split('/', 1)
                if len(path_parts) > 1:
                    file_path = unquote(path_parts[1])
                else:
                    file_path = unquote(parsed_url.path.strip('/'))
                
                if default_storage.exists(file_path):
                    default_storage.delete(file_path)
                    logger.info(f"✅ Deleted image from GCS when deleting block: {file_path}")
            except Exception as e:
                logger.error(f"❌ Failed to delete image from GCS when deleting block: {e}")
        
        try:
            block_id_str = str(block.id)
            lesson = block.lesson
            block_order = block.order
            
            block.delete()
            logger.info(f"✅ Deleted TutorX block: {block_id_str}")
            
            # Optionally: Reorder remaining blocks to fill the gap
            # This is optional - frontend handles ordering, but we can clean up gaps
            TutorXBlock.objects.filter(
                lesson=lesson,
                order__gt=block_order
            ).update(order=F('order') - 1)
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Error deleting block: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to delete block', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TutorXImageUploadView(APIView):
    """
    API view for uploading images for TutorX blocks.
    Uploads image to GCS, compresses it, and returns the URL.
    The URL is then saved directly in the TutorXBlock content field.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        Upload an image for TutorX blocks.
        
        Expected request:
        - image: Image file (JPEG, PNG, WebP, GIF)
        
        Returns:
        - image_url: GCS URL for the image
        - file_size: Size in bytes (after compression)
        - file_size_mb: Size in MB
        - file_extension: File extension
        - original_filename: Original filename
        - message: Success message
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can upload TutorX images'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Get uploaded image
            uploaded_image = request.FILES.get('image')
            if not uploaded_image:
                return Response(
                    {'error': 'No image provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate file size (max 10MB)
            max_size = 10 * 1024 * 1024  # 10MB in bytes
            if uploaded_image.size > max_size:
                return Response(
                    {'error': f'Image size exceeds maximum allowed size of 10MB. File size: {round(uploaded_image.size / (1024 * 1024), 2)}MB'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate file extension
            original_filename = uploaded_image.name
            file_extension = original_filename.split('.')[-1].lower() if '.' in original_filename else ''
            allowed_extensions = ['jpg', 'jpeg', 'png', 'webp', 'gif']
            
            if file_extension not in allowed_extensions:
                return Response(
                    {'error': f'Image extension "{file_extension}" not allowed. Allowed extensions: {", ".join(allowed_extensions)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if GCS is configured
            if not hasattr(settings, 'GS_BUCKET_NAME') or not settings.GS_BUCKET_NAME:
                return Response(
                    {'error': 'Google Cloud Storage is not configured. Please set GCS_BUCKET_NAME and GCS_PROJECT_ID environment variables.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            try:
                # Process image with Pillow
                img = PILImage.open(uploaded_image)
                
                # Convert RGBA/LA/P to RGB if needed
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create white background for transparent images
                    background = PILImage.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    if img.mode == 'RGBA':
                        background.paste(img, mask=img.split()[-1])
                    else:
                        background.paste(img)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize image to max 1920x1920 (maintains aspect ratio)
                max_size_full = (1920, 1920)
                img.thumbnail(max_size_full, PILImage.Resampling.LANCZOS)
                
                # Compress and save image
                output = BytesIO()
                img.save(
                    output,
                    format='JPEG',
                    quality=85,
                    optimize=True,
                    progressive=True
                )
                output.seek(0)
                
                # Generate unique filename
                unique_id = uuid.uuid4()
                base_name = original_filename.rsplit('.', 1)[0] if '.' in original_filename else 'image'
                # Sanitize base name
                base_name = ''.join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).strip()[:50]
                
                filename = f"{unique_id}-{base_name}.jpg"
                storage_path = f"tutorx-images/{filename}"
                
                # Upload to GCS
                file_content = ContentFile(output.getvalue())
                saved_path = default_storage.save(storage_path, file_content)
                file_url = default_storage.url(saved_path)
                if not file_url.startswith('http'):
                    file_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{saved_path}"
                
                # Get compressed file size
                file_size = len(output.getvalue())
                
                logger.info(f"✅ TutorX image uploaded: {file_url} (saved_path: {saved_path})")
                
                return Response({
                    'image_url': file_url,
                    'file_size': file_size,
                    'file_size_mb': round(file_size / (1024 * 1024), 2),
                    'file_extension': 'jpg',
                    'original_filename': original_filename,
                    'message': 'Image uploaded successfully'
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                logger.error(f"Error processing TutorX image: {e}", exc_info=True)
                return Response(
                    {'error': f'Failed to process image: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Exception as e:
            logger.error(f"Error in TutorX image upload: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to upload image', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TutorXImageDeleteView(APIView):
    """
    API view for deleting images from GCS.
    Extracts the file path from the GCS URL and deletes it.
    """
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        """
        Delete an image from GCS by URL.
        
        Expected request body:
        - image_url: GCS URL of the image to delete
        
        Returns:
        - message: Success message
        """
        try:
            # Check if user is a teacher
            if request.user.role != 'teacher':
                return Response(
                    {'error': 'Only teachers can delete TutorX images'},
                    status=status.HTTP_403_FORBIDDEN
                )

            image_url = request.data.get('image_url')
            if not image_url:
                return Response(
                    {'error': 'image_url is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if GCS is configured
            if not hasattr(settings, 'GS_BUCKET_NAME') or not settings.GS_BUCKET_NAME:
                return Response(
                    {'error': 'Google Cloud Storage is not configured'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Extract file path from GCS URL
            # URL format: https://storage.googleapis.com/BUCKET_NAME/path/to/file
            # or: https://storage.googleapis.com/BUCKET_NAME/path/to/file?query=params
            try:
                from urllib.parse import urlparse, unquote
                
                parsed_url = urlparse(image_url)
                # Remove leading slash and bucket name from path
                # Path format: /BUCKET_NAME/path/to/file
                path_parts = parsed_url.path.strip('/').split('/', 1)
                if len(path_parts) > 1:
                    file_path = path_parts[1]  # Get path after bucket name
                    # URL-decode the path
                    file_path = unquote(file_path)
                else:
                    # If no bucket name in path, assume it's already just the path
                    file_path = parsed_url.path.strip('/')
                    file_path = unquote(file_path)
                
                logger.info(f"🗑️ Deleting TutorX image from GCS: {file_path} (from URL: {image_url})")
                
                # Delete from GCS
                if default_storage.exists(file_path):
                    default_storage.delete(file_path)
                    logger.info(f"✅ Successfully deleted TutorX image from GCS: {file_path}")
                    return Response(
                        {'message': 'Image deleted successfully'},
                        status=status.HTTP_200_OK
                    )
                else:
                    logger.warning(f"⚠️ TutorX image file not found in GCS: {file_path}")
                    return Response(
                        {'message': 'Image file not found (may have already been deleted)'},
                        status=status.HTTP_200_OK
                    )
                    
            except Exception as e:
                logger.error(f"❌ Error deleting TutorX image from GCS: {e}", exc_info=True)
                return Response(
                    {'error': f'Failed to delete image: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Exception as e:
            logger.error(f"Error in TutorX image delete: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to delete image', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
