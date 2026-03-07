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

from .models import TutorXBlock, TutorXBlockActionConfig
from .services.ai import TutorXAIService
from .serializers import (
    BlockActionRequestSerializer,
    ExplainMoreResponseSerializer,
    GiveExamplesResponseSerializer,
    SimplifyResponseSerializer,
    SummarizeResponseSerializer,
    GenerateQuestionsResponseSerializer,
    StudentAskRequestSerializer,
    StudentAskResponseSerializer,
)
from settings.models import UserTutorXInstruction
from courses.models import Lesson
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from PIL import Image as PILImage
from io import BytesIO
import uuid
import json

logger = logging.getLogger(__name__)

# Placeholder prefix for pending images in multipart save (frontend sends __pending__<blockId>)
PENDING_IMAGE_PREFIX = "__pending__"


def upload_tutorx_image_file_to_gcs(uploaded_file) -> str:
    """
    Process and upload a TutorX image file to GCS (tutorx-images/).
    Reused by TutorXImageUploadView and by the multipart blocks PUT.
    Returns the public URL of the saved image.
    """
    original_filename = uploaded_file.name
    file_extension = original_filename.split('.')[-1].lower() if '.' in original_filename else ''
    allowed_extensions = ['jpg', 'jpeg', 'png', 'webp', 'gif']
    if file_extension not in allowed_extensions:
        raise ValueError(f'Image extension "{file_extension}" not allowed. Allowed: {", ".join(allowed_extensions)}')
    max_size = 10 * 1024 * 1024  # 10MB
    if uploaded_file.size > max_size:
        raise ValueError(f'Image size exceeds 10MB (got {round(uploaded_file.size / (1024 * 1024), 2)}MB)')
    if not hasattr(settings, 'GS_BUCKET_NAME') or not settings.GS_BUCKET_NAME:
        raise RuntimeError('Google Cloud Storage is not configured.')
    img = PILImage.open(uploaded_file)
    if img.mode in ('RGBA', 'LA', 'P'):
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
    max_size_full = (1920, 1920)
    img.thumbnail(max_size_full, PILImage.Resampling.LANCZOS)
    output = BytesIO()
    img.save(output, format='JPEG', quality=85, optimize=True, progressive=True)
    output.seek(0)
    unique_id = uuid.uuid4()
    base_name = original_filename.rsplit('.', 1)[0] if '.' in original_filename else 'image'
    base_name = ''.join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).strip()[:50]
    filename = f"{unique_id}-{base_name}.jpg"
    storage_path = f"tutorx-images/{filename}"
    file_content = ContentFile(output.getvalue())
    saved_path = default_storage.save(storage_path, file_content)
    file_url = default_storage.url(saved_path)
    if not file_url.startswith('http'):
        file_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{saved_path}"
    return file_url


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


class TutorXLessonContentView(APIView):
    """
    GET: Return lesson.tutorx_content (BlockNote JSON string, same as book page content).
    PUT: Save BlockNote JSON to lesson.tutorx_content. Multipart: content (JSON string),
         deleted_image_urls (JSON array), image_<blockId> (files). Backend uploads images,
         injects URLs into JSON, deletes removed images, saves final JSON.
    Same flow as book/material: one field, one request with images.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        if lesson.type != 'tutorx':
            return Response(
                {'error': 'This lesson is not a TutorX lesson'},
                status=status.HTTP_400_BAD_REQUEST
            )
        is_teacher = lesson.course.teacher == request.user
        is_student = False
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
        content = getattr(lesson, 'tutorx_content', '') or ''
        return Response({'content': content}, status=status.HTTP_200_OK)

    @transaction.atomic
    def put(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        if lesson.course.teacher != request.user:
            return Response(
                {'error': 'Only the course teacher can update content'},
                status=status.HTTP_403_FORBIDDEN
            )
        if lesson.type != 'tutorx':
            return Response(
                {'error': 'This lesson is not a TutorX lesson'},
                status=status.HTTP_400_BAD_REQUEST
            )
        content_raw = request.data.get('content') or request.POST.get('content', '[]')
        if isinstance(content_raw, list):
            content_raw = json.dumps(content_raw)
        deleted_raw = request.data.get('deleted_image_urls') or request.POST.get('deleted_image_urls', '[]')
        try:
            deleted_image_urls = json.loads(deleted_raw) if isinstance(deleted_raw, str) else list(deleted_raw) or []
        except (json.JSONDecodeError, TypeError):
            deleted_image_urls = []
        try:
            blocks = json.loads(content_raw) if isinstance(content_raw, str) else content_raw
            if not isinstance(blocks, list):
                blocks = []
        except (json.JSONDecodeError, TypeError):
            return Response(
                {'error': 'Invalid content JSON'},
                status=status.HTTP_400_BAD_REQUEST
            )
        uploaded_urls = {}
        for key in list(request.FILES.keys()):
            if key.startswith('image_'):
                block_id = key[6:]
                if not block_id:
                    continue
                try:
                    url = upload_tutorx_image_file_to_gcs(request.FILES[key])
                    uploaded_urls[block_id] = url
                except (ValueError, RuntimeError) as e:
                    return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        for image_url in deleted_image_urls:
            if not image_url or not isinstance(image_url, str):
                continue
            try:
                from urllib.parse import urlparse, unquote
                parsed_url = urlparse(image_url)
                path_parts = parsed_url.path.strip('/').split('/', 1)
                file_path = unquote(path_parts[1]) if len(path_parts) > 1 else unquote(parsed_url.path.strip('/'))
                delete_image_and_thumbnail(file_path)
            except Exception as e:
                logger.warning(f"Failed to delete image from GCS {image_url}: {e}")
        placeholder_prefix = PENDING_IMAGE_PREFIX

        def inject_urls_into_blocks(block_list):
            for b in block_list:
                if b.get('type') == 'image' and isinstance(b.get('props'), dict):
                    url_val = b['props'].get('url') or ''
                    if isinstance(url_val, str) and url_val.startswith(placeholder_prefix):
                        block_id = b.get('id')
                        if block_id and str(block_id) in uploaded_urls:
                            b['props']['url'] = uploaded_urls[str(block_id)]
                if isinstance(b.get('children'), list):
                    inject_urls_into_blocks(b['children'])

        inject_urls_into_blocks(blocks)
        lesson.tutorx_content = json.dumps(blocks)
        lesson.save(update_fields=['tutorx_content'])
        return Response({'content': lesson.tutorx_content}, status=status.HTTP_200_OK)


class TutorXLessonAskView(APIView):
    """
    POST: Student Ask AI - send sentence-based context + question, get AI answer.
    Same permission as GET blocks: teacher or enrolled student.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        if lesson.type != 'tutorx':
            return Response(
                {'error': 'This lesson is not a TutorX lesson'},
                status=status.HTTP_400_BAD_REQUEST
            )
        is_teacher = lesson.course.teacher == request.user
        is_student = False
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
        serializer = StudentAskRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            service = TutorXAIService()
            result = service.ask_student(
                lesson_title=data['lesson_title'],
                current_sentence=data['current_sentence'],
                selected_text=data['selected_text'],
                question=data['question'],
                context_before=data.get('context_before') or '',
                action_type=data.get('action_type'),
                temperature=0.7,
                max_tokens=None,
            )
            response_serializer = StudentAskResponseSerializer(data=result)
            if response_serializer.is_valid():
                return Response(response_serializer.validated_data, status=status.HTTP_200_OK)
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error in TutorXLessonAskView: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to get answer', 'details': str(e)},
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


def delete_image_and_thumbnail(file_path: str) -> tuple[bool, bool]:
    """
    Helper function to delete both the main image and its thumbnail from GCS.
    
    Args:
        file_path: The GCS path to the main image file
        
    Returns:
        Tuple of (main_image_deleted, thumbnail_deleted)
    """
    import os
    from pathlib import Path
    
    main_deleted = False
    thumb_deleted = False
    
    # Delete main image
    if default_storage.exists(file_path):
        try:
            default_storage.delete(file_path)
            main_deleted = True
            logger.info(f"✅ Deleted main image from GCS: {file_path}")
        except Exception as e:
            logger.error(f"❌ Failed to delete main image {file_path}: {e}")
    
    # Derive thumbnail path from main image path
    # Pattern 1: {storage_path}/{uuid}-{base_name}.jpg -> {storage_path}/thumbnails/{uuid}-{base_name}-thumb.jpg
    # Pattern 2: {storage_path}/images/{uuid}-{base_name}.jpg -> {storage_path}/images/thumbnails/{uuid}-{base_name}-thumb.jpg
    try:
        path_obj = Path(file_path)
        filename = path_obj.name  # e.g., "abc123-image.jpg"
        directory = path_obj.parent  # e.g., "assignment_images" or "assignment_files/images"
        
        # Extract UUID and base name from filename
        # Format: {uuid}-{base_name}.jpg
        if '-' in filename and filename.endswith('.jpg'):
            # Remove .jpg extension
            name_without_ext = filename[:-4]
            # Split by last dash to separate UUID from base name
            parts = name_without_ext.rsplit('-', 1)
            if len(parts) == 2:
                uuid_part = parts[0]
                base_name = parts[1]
                
                # Construct thumbnail filename
                thumb_filename = f"{uuid_part}-{base_name}-thumb.jpg"
                
                # Determine thumbnail directory based on main image directory
                if str(directory).endswith('/images') or 'images' in str(directory):
                    # Pattern 2: images are in a subdirectory, thumbnails are in images/thumbnails/
                    thumb_dir = directory / 'thumbnails'
                else:
                    # Pattern 1: thumbnails are in a thumbnails/ subdirectory at the same level
                    thumb_dir = directory / 'thumbnails'
                
                thumb_path = str(thumb_dir / thumb_filename)
                
                # Delete thumbnail
                if default_storage.exists(thumb_path):
                    try:
                        default_storage.delete(thumb_path)
                        thumb_deleted = True
                        logger.info(f"✅ Deleted thumbnail from GCS: {thumb_path}")
                    except Exception as e:
                        logger.error(f"❌ Failed to delete thumbnail {thumb_path}: {e}")
                else:
                    logger.debug(f"⚠️ Thumbnail not found (may not exist): {thumb_path}")
    except Exception as e:
        logger.warning(f"⚠️ Could not derive thumbnail path from {file_path}: {e}")
    
    return (main_deleted, thumb_deleted)


class TutorXImageDeleteView(APIView):
    """
    API view for deleting images from GCS.
    Extracts the file path from the GCS URL and deletes both the main image and its thumbnail.
    """
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        """
        Delete an image from GCS by URL (deletes both main image and thumbnail).
        
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
                
                logger.info(f"🗑️ Deleting TutorX image and thumbnail from GCS: {file_path} (from URL: {image_url})")
                
                # Delete both main image and thumbnail
                main_deleted, thumb_deleted = delete_image_and_thumbnail(file_path)
                
                if main_deleted or thumb_deleted:
                    messages = []
                    if main_deleted:
                        messages.append("main image")
                    if thumb_deleted:
                        messages.append("thumbnail")
                    message = f"Successfully deleted {', '.join(messages)}"
                    logger.info(f"✅ {message}")
                    return Response(
                        {'message': message},
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


class TutorXActionConfigListView(APIView):
    """
    GET: List all active TutorX block action configurations.
    
    Returns all active action configs with their display names and descriptions.
    Used by frontend to dynamically display available actions in the popup menu.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """
        Get all active action configs.
        
        Returns:
        {
            "actions": [
                {
                    "action_type": "explain_more",
                    "display_name": "Explain More",
                    "description": "Expand on block content with more detail"
                },
                ...
            ]
        }
        """
        try:
            # Get all active action configs, ordered by action_type
            configs = TutorXBlockActionConfig.objects.filter(
                is_active=True
            ).order_by('action_type')
            
            actions = []
            for config in configs:
                actions.append({
                    'action_type': config.action_type,
                    'display_name': config.display_name,
                    'description': config.description or '',
                })
            
            return Response({
                'actions': actions
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching action configs: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to fetch action configs', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
