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

from .models import TutorXBlock, TutorXBlockActionConfig, InteractiveVideo, InteractiveEvent
from .services.ai import TutorXAIService
from .services.storage import (
    delete_image_and_thumbnail,
    file_path_from_tutorx_image_url,
    collect_image_urls_from_blocknote_string,
    collect_image_urls_from_event_payload,
)
from .serializers import (
    BlockActionRequestSerializer,
    ExplainMoreResponseSerializer,
    GiveExamplesResponseSerializer,
    SimplifyResponseSerializer,
    SummarizeResponseSerializer,
    GenerateQuestionsResponseSerializer,
    DrawExplainerImageResponseSerializer,
    StudentAskRequestSerializer,
    StudentAskResponseSerializer,
    InteractiveEventSerializer,
    InteractiveVideoSerializer,
)
from settings.models import UserTutorXInstruction
from courses.models import Lesson, AudioVideoMaterial
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from PIL import Image as PILImage
from io import BytesIO
import uuid
import json
import os
import tempfile

from courses.hls_utils import (
    convert_to_hls,
    upload_hls_to_gcs,
    delete_hls_from_gcs,
    HLSConversionError,
    HLSUploadError,
)

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


def upload_tutorx_video_file_to_gcs(uploaded_file) -> str:
    """
    Upload a TutorX video file to GCS (tutorx-media/). No image processing.
    Used by the multipart content PUT when the file extension is video.
    Returns the public URL of the saved file.
    """
    original_filename = uploaded_file.name
    file_extension = original_filename.split('.')[-1].lower() if '.' in original_filename else ''
    allowed_extensions = ['mp4', 'webm', 'ogg', 'mov', 'm4v']
    if file_extension not in allowed_extensions:
        raise ValueError(
            f'Video extension "{file_extension}" not allowed. Allowed: {", ".join(allowed_extensions)}'
        )
    max_size = 500 * 1024 * 1024  # 500MB
    if uploaded_file.size > max_size:
        raise ValueError(
            f'Video size exceeds 500MB (got {round(uploaded_file.size / (1024 * 1024), 2)}MB)'
        )
    if not hasattr(settings, 'GS_BUCKET_NAME') or not settings.GS_BUCKET_NAME:
        raise RuntimeError('Google Cloud Storage is not configured.')
    unique_id = uuid.uuid4()
    base_name = original_filename.rsplit('.', 1)[0] if '.' in original_filename else 'video'
    base_name = ''.join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).strip()[:50]
    filename = f"{unique_id}-{base_name}.{file_extension}"
    storage_path = f"tutorx-media/{filename}"
    saved_path = default_storage.save(storage_path, uploaded_file)
    file_url = default_storage.url(saved_path)
    if not file_url.startswith('http'):
        file_url = f"https://storage.googleapis.com/{settings.GS_BUCKET_NAME}/{saved_path}"
    return file_url


def create_audio_video_material_for_tutorx(
    file,
    uploaded_by,
    existing_material: AudioVideoMaterial | None = None,
) -> AudioVideoMaterial:
    """
    Create or replace an AudioVideoMaterial for a TutorX interactive video.

    - Converts video to HLS using the shared courses.hls_utils helpers.
    - Uploads playlist + segments to GCS under a stable prefix.
    - If existing_material is provided, deletes the old HLS assets and
      updates that row instead of creating a new one.
    """
    original_filename = getattr(file, "name", "video.mp4")

    max_size = 500 * 1024 * 1024  # 500MB in bytes
    if file.size > max_size:
        raise ValueError(
            f"File size exceeds maximum allowed size of 500MB. "
            f"File size: {round(file.size / (1024 * 1024), 2)}MB"
        )

    import mimetypes

    file_extension = original_filename.split(".")[-1].lower() if "." in original_filename else "mp4"
    mime_type = file.content_type or mimetypes.guess_type(original_filename)[0] or "video/mp4"

    if not mime_type.startswith("video/"):
        raise ValueError("Interactive TutorX videos must be video files.")

    temp_video_path: str | None = None
    local_hls_dir = None

    import uuid as uuid_module

    if existing_material is not None:
        material_id = existing_material.id
        try:
            delete_hls_from_gcs(f"hls/audio-video/{material_id}/")
        except Exception:
            logger.warning("Failed to delete old HLS assets for material %s", material_id)
    else:
        material_id = uuid_module.uuid4()

    gcs_prefix = f"hls/audio-video/{material_id}/"

    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=os.path.splitext(original_filename)[1] or ".mp4",
        ) as tmp:
            for chunk in file.chunks():
                tmp.write(chunk)
            temp_video_path = tmp.name

        local_hls_dir = convert_to_hls(temp_video_path)
        playlist_url = upload_hls_to_gcs(local_hls_dir, gcs_prefix)

        safe_file_name = f"hls/audio-video/{material_id}/playlist.m3u8"
        safe_original_filename = (
            original_filename[:200] if len(original_filename) > 200 else original_filename
        )

        if existing_material is None:
            av_material = AudioVideoMaterial.objects.create(
                file_name=safe_file_name,
                original_filename=safe_original_filename,
                file_url=playlist_url,
                file_size=file.size,
                file_extension=file_extension,
                mime_type=mime_type,
                uploaded_by=uploaded_by,
                lesson_material=None,
            )
        else:
            existing_material.file_name = safe_file_name
            existing_material.original_filename = safe_original_filename
            existing_material.file_url = playlist_url
            existing_material.file_size = file.size
            existing_material.file_extension = file_extension
            existing_material.mime_type = mime_type
            existing_material.uploaded_by = uploaded_by
            existing_material.save()
            av_material = existing_material

        logger.info(
            "TutorX InteractiveVideo AudioVideoMaterial saved: %s",
            av_material.id,
        )
        return av_material
    except (HLSConversionError, HLSUploadError) as e:
        logger.exception(
            "HLS conversion/upload failed for TutorX interactive video: %s",
            e,
        )
        try:
            delete_hls_from_gcs(gcs_prefix)
        except Exception:
            pass
        raise
    finally:
        if temp_video_path and os.path.exists(temp_video_path):
            try:
                os.unlink(temp_video_path)
            except Exception:
                pass
        if local_hls_dir is not None:
            path_str = str(local_hls_dir)
            if os.path.exists(path_str):
                try:
                    import shutil

                    shutil.rmtree(path_str, ignore_errors=True)
                except Exception:
                    pass


# Video extensions for dispatch in content PUT (must match upload_tutorx_video_file_to_gcs)
TUTORX_VIDEO_EXTENSIONS = {'mp4', 'webm', 'ogg', 'mov', 'm4v'}


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
        valid_actions = ['explain_more', 'give_examples', 'simplify', 'summarize', 'generate_questions', 'draw_explainer_image']
        
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
                'draw_explainer_image': DrawExplainerImageResponseSerializer,
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


class __REMOVED_TutorXBlockListView_START(APIView):
    pass  # placeholder to delete
    def _put_placeholder(self, request, lesson_id):
        """Bulk update blocks - handles create, update, and delete.
        Accepts JSON body { blocks } or multipart/form-data with blocks, deleted_image_urls, and image_<blockId> files.
        When multipart: uploads images to GCS, injects URLs into blocks, deletes removed images, then persists blocks.
        """
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
        
        # Detect multipart (single-request save with images)
        is_multipart = (
            request.content_type
            and 'multipart/form-data' in request.content_type
        ) or bool(request.FILES)
        
        if is_multipart:
            try:
                blocks_raw = request.data.get('blocks') or request.POST.get('blocks', '[]')
                if isinstance(blocks_raw, str):
                    blocks_data = json.loads(blocks_raw)
                else:
                    blocks_data = list(blocks_raw)
                deleted_raw = request.data.get('deleted_image_urls') or request.POST.get('deleted_image_urls', '[]')
                if isinstance(deleted_raw, str):
                    deleted_image_urls = json.loads(deleted_raw)
                else:
                    deleted_image_urls = list(deleted_raw) if deleted_raw else []
            except (json.JSONDecodeError, TypeError) as e:
                return Response(
                    {'error': f'Invalid blocks or deleted_image_urls JSON: {e}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            uploaded_urls = {}  # block_id -> GCS URL
            try:
                for key in list(request.FILES.keys()):
                    if key.startswith('image_'):
                        block_id = key[6:]  # len('image_') == 6
                        if not block_id:
                            continue
                        file_obj = request.FILES[key]
                        url = upload_tutorx_image_file_to_gcs(file_obj)
                        uploaded_urls[block_id] = url
                for block in blocks_data:
                    block_id = block.get('id')
                    content = block.get('content', '') or ''
                    meta = block.get('metadata') or {}
                    image_url = meta.get('image_url', '') or content
                    placeholder = f"{PENDING_IMAGE_PREFIX}{block_id}"
                    if block_id and (content == placeholder or image_url == placeholder) and block_id in uploaded_urls:
                        url = uploaded_urls[block_id]
                        block['content'] = url
                        if 'metadata' not in block:
                            block['metadata'] = {}
                        block['metadata']['image_url'] = url
                        # FormFieldBlockNoteEditor style: keep block_note_block in sync so frontend loads correct URL
                        bnb = block['metadata'].get('block_note_block')
                        if isinstance(bnb, dict) and bnb.get('type') == 'image':
                            if 'props' not in bnb:
                                bnb['props'] = {}
                            bnb['props']['url'] = url
                for image_url in deleted_image_urls:
                    if not image_url or not isinstance(image_url, str):
                        continue
                    try:
                        from urllib.parse import urlparse, unquote
                        parsed_url = urlparse(image_url)
                        path_parts = parsed_url.path.strip('/').split('/', 1)
                        if len(path_parts) > 1:
                            file_path = unquote(path_parts[1])
                        else:
                            file_path = unquote(parsed_url.path.strip('/'))
                        delete_image_and_thumbnail(file_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete image from GCS {image_url}: {e}")
            except ValueError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except RuntimeError as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
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
            
            # Delete images from GCS before deleting blocks (including thumbnails)
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
                        
                        # Delete both main image and thumbnail
                        main_deleted, thumb_deleted = delete_image_and_thumbnail(file_path)
                        if main_deleted or thumb_deleted:
                            logger.info(f"✅ Deleted image and thumbnail from GCS when deleting block: {file_path}")
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
                    
                    # If image URL changed, delete old image and thumbnail from GCS
                    if old_image_url and old_image_url != new_image_url:
                        try:
                            from urllib.parse import urlparse, unquote
                            parsed_url = urlparse(old_image_url)
                            path_parts = parsed_url.path.strip('/').split('/', 1)
                            if len(path_parts) > 1:
                                file_path = unquote(path_parts[1])
                            else:
                                file_path = unquote(parsed_url.path.strip('/'))
                            
                            # Delete both main image and thumbnail
                            main_deleted, thumb_deleted = delete_image_and_thumbnail(file_path)
                            if main_deleted or thumb_deleted:
                                logger.info(f"✅ Deleted old image and thumbnail from GCS when replacing: {file_path}")
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
        response_data = {'content': content}
        if hasattr(lesson, 'interactive_video'):
            from .serializers import InteractiveVideoSerializer

            response_data['interactive_video'] = InteractiveVideoSerializer(
                lesson.interactive_video
            ).data
        return Response(response_data, status=status.HTTP_200_OK)

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
        if content_raw is None or (isinstance(content_raw, str) and not content_raw.strip()):
            content_raw = '[]'
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
        event_uploaded_urls = {}  # (event_index, field, block_id) -> url
        for key in list(request.FILES.keys()):
            if not key.startswith('image_'):
                continue
            suffix = key[6:]  # after "image_"
            uploaded_file = request.FILES[key]
            ext = (uploaded_file.name or '').split('.')[-1].lower() if '.' in (uploaded_file.name or '') else ''
            try:
                if ext in TUTORX_VIDEO_EXTENSIONS:
                    url = upload_tutorx_video_file_to_gcs(uploaded_file)
                else:
                    url = upload_tutorx_image_file_to_gcs(uploaded_file)
            except (ValueError, RuntimeError) as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            if suffix.startswith('ev_'):
                parts = suffix[3:].split('_')  # after "ev_": e.g. "0_prompt_abc123" -> ["0","prompt","abc123"]
                if len(parts) >= 3:
                    try:
                        event_index = int(parts[0])
                        block_id = parts[-1]
                        field = '_'.join(parts[1:-1])
                        event_uploaded_urls[(event_index, field, block_id)] = url
                    except (ValueError, IndexError):
                        pass
            else:
                if suffix:
                    uploaded_urls[suffix] = url
        for image_url in deleted_image_urls:
            file_path = file_path_from_tutorx_image_url(image_url)
            if file_path:
                try:
                    delete_image_and_thumbnail(file_path)
                except Exception as e:
                    logger.warning("Failed to delete image from GCS %s: %s", image_url[:80], e)
        placeholder_prefix = PENDING_IMAGE_PREFIX

        def inject_urls_into_blocks(block_list):
            for b in block_list:
                block_type = b.get('type')
                if block_type in ('image', 'video', 'audio') and isinstance(b.get('props'), dict):
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

        # --- Interactive video handling (optional, backwards compatible) ---
        interactive_video_raw = request.data.get('interactive_video')
        interactive_video_data = None
        if interactive_video_raw:
            try:
                interactive_video_data = (
                    json.loads(interactive_video_raw)
                    if isinstance(interactive_video_raw, str)
                    else interactive_video_raw
                )
            except (json.JSONDecodeError, TypeError):
                return Response(
                    {'error': 'Invalid interactive_video JSON'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        interactive_video_file = request.FILES.get('interactive_video_file')

        interactive_video_obj = None
        if interactive_video_data is not None or interactive_video_file:
            interactive_video_obj, _created = InteractiveVideo.objects.get_or_create(
                lesson=lesson
            )

            # If no new file and payload says no video (video_source 'none'), remove existing video and delete from GCS.
            video_source = (interactive_video_data or {}).get('video_source') if interactive_video_data else None
            if not interactive_video_file and video_source == 'none':
                old_av = interactive_video_obj.audio_video_material
                if old_av:
                    old_av.delete()
                    interactive_video_obj.audio_video_material = None
                    interactive_video_obj.save(update_fields=['audio_video_material'])

            if interactive_video_file:
                # Two-step replace: delete old material (and its GCS files) first, then create new one.
                # Reusing the same row + delete_hls_from_gcs in the helper was not removing old GCS; material.delete() does.
                old_av = None
                if getattr(interactive_video_obj, "audio_video_material_id", None):
                    try:
                        old_av = AudioVideoMaterial.objects.get(
                            pk=interactive_video_obj.audio_video_material_id
                        )
                    except AudioVideoMaterial.DoesNotExist:
                        pass
                if old_av:
                    old_av.delete()
                    interactive_video_obj.audio_video_material = None
                    interactive_video_obj.save(update_fields=['audio_video_material'])
                try:
                    av_material = create_audio_video_material_for_tutorx(
                        file=interactive_video_file,
                        uploaded_by=request.user,
                        existing_material=None,
                    )
                except (ValueError, HLSConversionError, HLSUploadError) as e:
                    return Response(
                        {'error': str(e)}, status=status.HTTP_400_BAD_REQUEST
                    )

                interactive_video_obj.audio_video_material = av_material
                interactive_video_obj.save(update_fields=['audio_video_material'])

            events_payload = (
                (interactive_video_data or {}).get('events')
                if interactive_video_data
                else []
            )

            def inject_urls_into_blocknote_string(field_json, block_id_to_url):
                if not field_json or not isinstance(field_json, str):
                    return field_json
                try:
                    blocks = json.loads(field_json)
                except (json.JSONDecodeError, TypeError):
                    return field_json
                if not isinstance(blocks, list):
                    return field_json

                def walk(block_list):
                    for b in block_list:
                        if b.get('type') in ('image', 'video', 'audio') and isinstance(b.get('props'), dict):
                            url_val = b['props'].get('url') or ''
                            if isinstance(url_val, str) and url_val.startswith(placeholder_prefix):
                                block_id = b.get('id')
                                if block_id and str(block_id) in block_id_to_url:
                                    b['props']['url'] = block_id_to_url[str(block_id)]
                        if isinstance(b.get('children'), list):
                            walk(b['children'])

                walk(blocks)
                return json.dumps(blocks)

            for i, ev in enumerate(events_payload or []):
                event_type = ev.get('type') or ev.get('event_type')
                if event_type == 'pop_quiz' and ev.get('questions'):
                    q0 = (ev.get('questions') or [{}])[0] if ev.get('questions') else {}
                    if isinstance(q0, dict):
                        block_id_to_url_prompt = {
                            bid: u for (ei, f, bid), u in event_uploaded_urls.items()
                            if ei == i and f == 'q0_prompt'
                        }
                        block_id_to_url_expl = {
                            bid: u for (ei, f, bid), u in event_uploaded_urls.items()
                            if ei == i and f == 'q0_explanation'
                        }
                        if block_id_to_url_prompt or block_id_to_url_expl:
                            q0 = dict(q0)
                            if block_id_to_url_prompt and q0.get('prompt'):
                                q0['prompt'] = inject_urls_into_blocknote_string(q0['prompt'], block_id_to_url_prompt)
                            if block_id_to_url_expl and q0.get('explanation'):
                                q0['explanation'] = inject_urls_into_blocknote_string(q0['explanation'], block_id_to_url_expl)
                            ev['questions'] = [q0] + list((ev.get('questions') or [])[1:])
                else:
                    for field_key, field_name in [
                        ('prompt', 'prompt'),
                        ('question', 'question'),
                        ('explanation', 'explanation'),
                        ('explanationYes', 'explanation_yes'),
                        ('explanationNo', 'explanation_no'),
                        ('modelAnswer', 'model_answer'),
                    ]:
                        block_id_to_url = {
                            bid: event_uploaded_urls[(i, field_name, bid)]
                            for (ei, f, bid), u in event_uploaded_urls.items()
                            if ei == i and f == field_name
                        }
                        if block_id_to_url and ev.get(field_key):
                            ev[field_key] = inject_urls_into_blocknote_string(ev[field_key], block_id_to_url)

            # Delete from GCS any images that were in event content but are no longer (remove or replace).
            existing_events = list(
                InteractiveEvent.objects.filter(interactive_video=interactive_video_obj)
            )
            old_urls = set()
            for ex in existing_events:
                for field in ("prompt", "explanation", "explanation_yes", "explanation_no", "model_answer"):
                    val = getattr(ex, field, None)
                    if isinstance(val, str):
                        old_urls.update(collect_image_urls_from_blocknote_string(val))
            new_urls = set()
            for ev in events_payload or []:
                new_urls.update(collect_image_urls_from_event_payload(ev))
            for image_url in old_urls - new_urls:
                file_path = file_path_from_tutorx_image_url(image_url)
                if file_path:
                    try:
                        delete_image_and_thumbnail(file_path)
                    except Exception as e:
                        logger.warning(
                            "Failed to delete event image from GCS %s: %s",
                            image_url[:80] if image_url else "",
                            e,
                        )

            InteractiveEvent.objects.filter(
                interactive_video=interactive_video_obj
            ).delete()

            for ev in events_payload or []:
                # Frontend may send 'type' (camelCase) or 'event_type' (from re-sent API response).
                event_type = ev.get('type') or ev.get('event_type')
                if not event_type:
                    logger.warning(
                        "TutorX interactive event missing type/event_type, skipping: %s",
                        ev.get('id'),
                    )
                    continue

                # Default mapping (true/false, essay, yes/no, or future types).
                # Accept both camelCase and snake_case so re-sent API payloads work.
                prompt = ev.get('prompt') or ev.get('question', '')
                explanation = ev.get('explanation', '')
                options = ev.get('options')
                correct_option_index = ev.get('correctOptionIndex')

                # For multiple choice ('pop_quiz'), the frontend currently nests data
                # under a single-element `questions` array.
                if event_type == 'pop_quiz' and ev.get('questions'):
                    first_q = (ev.get('questions') or [])[0] or {}
                    prompt = (
                        first_q.get('prompt')
                        or first_q.get('question', '')
                        or prompt
                    )
                    explanation = first_q.get('explanation', '') or explanation
                    options = first_q.get('options', options)
                    correct_option_index = first_q.get('correctOptionIndex', correct_option_index)

                InteractiveEvent.objects.create(
                    interactive_video=interactive_video_obj,
                    event_type=event_type,
                    timestamp_seconds=ev.get('timestampSeconds') or ev.get('timestamp_seconds', 0),
                    title=ev.get('title', ''),
                    prompt=prompt,
                    explanation=explanation,
                    options=options,
                    correct_option_index=correct_option_index if correct_option_index is not None else ev.get('correct_option_index'),
                    yes_label=ev.get('yesLabel') or ev.get('yes_label', ''),
                    no_label=ev.get('noLabel') or ev.get('no_label', ''),
                    explanation_yes=ev.get('explanationYes') or ev.get('explanation_yes', ''),
                    explanation_no=ev.get('explanationNo') or ev.get('explanation_no', ''),
                    correct_answer=ev.get('correctAnswer') if ev.get('correctAnswer') is not None else ev.get('correct_answer'),
                    model_answer=ev.get('modelAnswer') or ev.get('model_answer', ''),
                )

        from .services.lesson_chat import invalidate_lesson_chat_cache

        invalidate_lesson_chat_cache(lesson_id)

        from .serializers import InteractiveVideoSerializer

        response_data = {'content': lesson.tutorx_content}
        if hasattr(lesson, 'interactive_video'):
            response_data['interactive_video'] = InteractiveVideoSerializer(
                lesson.interactive_video
            ).data

        return Response(response_data, status=status.HTTP_200_OK)


class TutorXLessonVideoView(APIView):
    """
    Manage the interactive video (HLS) for a TutorX lesson.

    - GET: return current interactive video id and video_url (if any).
    - PUT: upload/replace/remove interactive video without touching content or events.
    """

    permission_classes = [permissions.IsAuthenticated]

    def _get_lesson_and_check_access(self, request, lesson_id, write: bool):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        if lesson.type != 'tutorx':
            return None, Response(
                {'error': 'This lesson is not a TutorX lesson'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_teacher = lesson.course.teacher == request.user
        if write:
            if not is_teacher:
                return None, Response(
                    {'error': 'Only the course teacher can update the interactive video'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            if not is_teacher:
                is_student = False
                if hasattr(request.user, 'student_profile'):
                    from student.models import EnrolledCourse

                    is_student = EnrolledCourse.objects.filter(
                        student_profile=request.user.student_profile,
                        course=lesson.course,
                        status__in=['active', 'completed'],
                    ).exists()
                if not is_student:
                    return None, Response(
                        {
                            'error': (
                                'Only the course teacher or enrolled students can '
                                'access this lesson video'
                            )
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
        return lesson, None

    def get(self, request, lesson_id):
        lesson, error = self._get_lesson_and_check_access(
            request, lesson_id, write=False
        )
        if error is not None:
            return error

        data = {
            'interactive_video_id': None,
            'video_url': None,
        }
        if hasattr(lesson, 'interactive_video'):
            iv = lesson.interactive_video
            data['interactive_video_id'] = str(iv.id)
            if iv.audio_video_material:
                data['video_url'] = iv.audio_video_material.file_url
        return Response(data, status=status.HTTP_200_OK)

    @transaction.atomic
    def put(self, request, lesson_id):
        lesson, error = self._get_lesson_and_check_access(
            request, lesson_id, write=True
        )
        if error is not None:
            return error

        interactive_video, _created = InteractiveVideo.objects.get_or_create(
            lesson=lesson
        )

        video_source = (request.data.get('video_source') or '').strip() or 'existing'
        video_file = request.FILES.get('video_file')

        # Remove video
        if video_source == 'none':
            old_av = interactive_video.audio_video_material
            if old_av:
                try:
                    old_av.delete()
                except Exception as e:
                    logger.warning(
                        "Failed to delete AudioVideoMaterial for interactive_video %s: %s",
                        interactive_video.id,
                        e,
                    )
                interactive_video.audio_video_material = None
                interactive_video.save(update_fields=['audio_video_material'])

        # Upload / replace video
        elif video_source == 'new_upload' and video_file:
            old_av = interactive_video.audio_video_material
            if old_av:
                try:
                    old_av.delete()
                except Exception as e:
                    logger.warning(
                        "Failed to delete old AudioVideoMaterial for interactive_video %s: %s",
                        interactive_video.id,
                        e,
                    )
                interactive_video.audio_video_material = None
                interactive_video.save(update_fields=['audio_video_material'])
            try:
                av_material = create_audio_video_material_for_tutorx(
                    file=video_file,
                    uploaded_by=request.user,
                    existing_material=None,
                )
            except (ValueError, HLSConversionError, HLSUploadError) as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

            interactive_video.audio_video_material = av_material
            interactive_video.save(update_fields=['audio_video_material'])

        # else: video_source == 'existing' or no recognized change -> no-op

        data = {
            'interactive_video_id': str(interactive_video.id),
            'video_url': None,
        }
        if interactive_video.audio_video_material:
            data['video_url'] = interactive_video.audio_video_material.file_url

        return Response(data, status=status.HTTP_200_OK)


class TutorXLessonEventsView(APIView):
    """
    GET: Return interactive events for the lesson's interactive video.
    PUT: Replace all events (JSON body { "events": [...] }). Creates InteractiveVideo if needed.
    Same permission as video: teacher can write; teacher or enrolled student can read.
    """

    permission_classes = [permissions.IsAuthenticated]

    def _get_lesson_and_check_access(self, request, lesson_id, write: bool):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        if lesson.type != 'tutorx':
            return None, Response(
                {'error': 'This lesson is not a TutorX lesson'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        is_teacher = lesson.course.teacher == request.user
        if write:
            if not is_teacher:
                return None, Response(
                    {'error': 'Only the course teacher can update interactive events'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            if not is_teacher:
                is_student = False
                if hasattr(request.user, 'student_profile'):
                    from student.models import EnrolledCourse
                    is_student = EnrolledCourse.objects.filter(
                        student_profile=request.user.student_profile,
                        course=lesson.course,
                        status__in=['active', 'completed'],
                    ).exists()
                if not is_student:
                    return None, Response(
                        {
                            'error': (
                                'Only the course teacher or enrolled students can '
                                'access this lesson\'s events'
                            )
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
        return lesson, None

    def get(self, request, lesson_id):
        lesson, error = self._get_lesson_and_check_access(
            request, lesson_id, write=False
        )
        if error is not None:
            return error
        events_data = []
        if hasattr(lesson, 'interactive_video'):
            iv = lesson.interactive_video
            events_qs = InteractiveEvent.objects.filter(
                interactive_video=iv
            ).order_by('timestamp_seconds', 'id')
            events_data = InteractiveEventSerializer(events_qs, many=True).data
        return Response({'events': events_data}, status=status.HTTP_200_OK)

    @transaction.atomic
    def put(self, request, lesson_id):
        lesson, error = self._get_lesson_and_check_access(
            request, lesson_id, write=True
        )
        if error is not None:
            return error

        # Parse events: JSON body or multipart (events in POST as JSON string)
        try:
            body = request.data if getattr(request, 'data', None) else {}
            if not body and request.body and not request.FILES:
                body = json.loads(request.body)
            events_raw = (body.get('events') if body else None) or request.POST.get('events')
            if events_raw is None:
                events_raw = []
            if isinstance(events_raw, str):
                events_raw = json.loads(events_raw)
            if not isinstance(events_raw, list):
                return Response(
                    {'error': 'events must be an array'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            events_payload = events_raw
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            return Response(
                {'error': f'Invalid JSON: {e}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Multipart: upload image_ev_<blockId> files and build block_id -> url
        block_id_to_url = {}
        for key in list(request.FILES.keys()):
            if not key.startswith('image_ev_'):
                continue
            block_id = key[9:]  # after "image_ev_"
            if not block_id:
                continue
            uploaded_file = request.FILES[key]
            try:
                url = upload_tutorx_image_file_to_gcs(uploaded_file)
                block_id_to_url[block_id] = url
            except (ValueError, RuntimeError) as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        def inject_urls_into_blocknote_string(field_json, id_to_url):
            if not field_json or not isinstance(field_json, str):
                return field_json
            try:
                blocks = json.loads(field_json)
            except (json.JSONDecodeError, TypeError):
                return field_json
            if not isinstance(blocks, list):
                return field_json

            def walk(block_list):
                for b in block_list:
                    if b.get('type') in ('image', 'video', 'audio') and isinstance(b.get('props'), dict):
                        url_val = b['props'].get('url') or ''
                        if isinstance(url_val, str) and url_val.startswith(PENDING_IMAGE_PREFIX):
                            block_id = url_val[len(PENDING_IMAGE_PREFIX):]
                            if block_id and block_id in id_to_url:
                                b['props']['url'] = id_to_url[block_id]
                    if isinstance(b.get('children'), list):
                        walk(b['children'])

            walk(blocks)
            return json.dumps(blocks)

        # Replace __pending__<blockId> in event content fields
        for ev in events_payload:
            if ev.get('questions'):
                for i, q in enumerate(ev.get('questions') or []):
                    if isinstance(q, dict):
                        if q.get('prompt'):
                            q['prompt'] = inject_urls_into_blocknote_string(q['prompt'], block_id_to_url)
                        if q.get('explanation'):
                            q['explanation'] = inject_urls_into_blocknote_string(q['explanation'], block_id_to_url)
            for field_key in ('prompt', 'question', 'explanation', 'explanationYes', 'explanation_yes',
                              'explanationNo', 'explanation_no', 'modelAnswer', 'model_answer'):
                if ev.get(field_key):
                    ev[field_key] = inject_urls_into_blocknote_string(ev[field_key], block_id_to_url)

        # Delete from GCS any URLs in deleted_image_urls (multipart)
        deleted_raw = body.get('deleted_image_urls') if body else None
        if deleted_raw is None and request.POST.get('deleted_image_urls'):
            try:
                deleted_raw = json.loads(request.POST.get('deleted_image_urls'))
            except (json.JSONDecodeError, TypeError):
                deleted_raw = []
        if isinstance(deleted_raw, list):
            for image_url in deleted_raw:
                if not isinstance(image_url, str):
                    continue
                file_path = file_path_from_tutorx_image_url(image_url)
                if file_path:
                    try:
                        delete_image_and_thumbnail(file_path)
                    except Exception as e:
                        logger.warning(
                            'Failed to delete event image from GCS %s: %s',
                            image_url[:80] if image_url else '',
                            e,
                        )

        interactive_video_obj, _ = InteractiveVideo.objects.get_or_create(
            lesson=lesson
        )

        # Collect old event image URLs for GCS cleanup
        existing_events = list(
            InteractiveEvent.objects.filter(interactive_video=interactive_video_obj)
        )
        old_urls = set()
        for ex in existing_events:
            for field in (
                'prompt', 'explanation', 'explanation_yes', 'explanation_no',
                'model_answer',
            ):
                val = getattr(ex, field, None)
                if isinstance(val, str):
                    old_urls.update(
                        collect_image_urls_from_blocknote_string(val)
                    )
        new_urls = set()
        for ev in events_payload:
            new_urls.update(collect_image_urls_from_event_payload(ev))
        for image_url in old_urls - new_urls:
            file_path = file_path_from_tutorx_image_url(image_url)
            if file_path:
                try:
                    delete_image_and_thumbnail(file_path)
                except Exception as e:
                    logger.warning(
                        'Failed to delete event image from GCS %s: %s',
                        (image_url[:80] if image_url else ''),
                        e,
                    )

        InteractiveEvent.objects.filter(
            interactive_video=interactive_video_obj
        ).delete()

        for ev in events_payload:
            event_type = ev.get('type') or ev.get('event_type')
            if not event_type:
                logger.warning(
                    'TutorX interactive event missing type/event_type, skipping: %s',
                    ev.get('id'),
                )
                continue
            prompt = ev.get('prompt') or ev.get('question', '')
            explanation = ev.get('explanation', '')
            options = ev.get('options')
            correct_option_index = ev.get('correctOptionIndex')
            if event_type == 'pop_quiz' and ev.get('questions'):
                first_q = (ev.get('questions') or [])[0] or {}
                prompt = (
                    first_q.get('prompt')
                    or first_q.get('question', '')
                    or prompt
                )
                explanation = first_q.get('explanation', '') or explanation
                options = first_q.get('options', options)
                correct_option_index = first_q.get(
                    'correctOptionIndex', first_q.get('correct_option_index')
                )
            InteractiveEvent.objects.create(
                interactive_video=interactive_video_obj,
                event_type=event_type,
                timestamp_seconds=ev.get('timestampSeconds') or ev.get('timestamp_seconds', 0),
                title=ev.get('title', ''),
                prompt=prompt,
                explanation=explanation,
                options=options,
                correct_option_index=(
                    correct_option_index
                    if correct_option_index is not None
                    else ev.get('correct_option_index')
                ),
                yes_label=ev.get('yesLabel') or ev.get('yes_label', ''),
                no_label=ev.get('noLabel') or ev.get('no_label', ''),
                explanation_yes=ev.get('explanationYes') or ev.get('explanation_yes', ''),
                explanation_no=ev.get('explanationNo') or ev.get('explanation_no', ''),
                correct_answer=(
                    ev.get('correctAnswer')
                    if ev.get('correctAnswer') is not None
                    else ev.get('correct_answer')
                ),
                model_answer=ev.get('modelAnswer') or ev.get('model_answer', ''),
            )

        events_qs = InteractiveEvent.objects.filter(
            interactive_video=interactive_video_obj
        ).order_by('timestamp_seconds', 'id')
        events_data = InteractiveEventSerializer(events_qs, many=True).data
        return Response({'events': events_data}, status=status.HTTP_200_OK)


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


class LessonChatView(APIView):
    """
    POST: Lesson chat window (list-based, no WebSocket).
    Request: { "message": "...", "conversation": [ { "role", "content" or "type", "data" } ] }
    Response: { "response_type": "text"|"qanda"|"explainer_image", "content" or "data", "conversation": updated_list }
    AI infers intent (explain_better, generate_questions, draw_explainer_image) via function calling; we dispatch to the matching handler. Permission: course teacher or enrolled student.
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

        from .serializers import LessonChatRequestSerializer
        from .services.lesson_chat import get_lesson_context, run_lesson_chat

        serializer = LessonChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        message = serializer.validated_data['message']
        conversation = list(serializer.validated_data.get('conversation') or [])

        # Load lesson context (cached by lesson_id)
        lesson_context = get_lesson_context(lesson_id)

        # AI-based intent: model infers intent and we dispatch to the right handler
        if lesson_context:
            try:
                response_type, content, data, assistant_msg = run_lesson_chat(
                    lesson_context=lesson_context,
                    user_message=message,
                    conversation=conversation,
                )
            except Exception as e:
                logger.exception("Lesson chat run_lesson_chat failed: %s", e)
                content = f"Something went wrong. ({str(e)})"
                assistant_msg = {'role': 'assistant', 'type': 'text', 'content': content}
                response_type, data = 'text', None
        else:
            content = "Lesson content is not available."
            assistant_msg = {'role': 'assistant', 'type': 'text', 'content': content}
            response_type, data = 'text', None

        user_msg = {'role': 'user', 'content': message}
        updated_conversation = conversation + [user_msg, assistant_msg]

        payload = {
            'response_type': response_type,
            'conversation': updated_conversation,
        }
        if response_type in ('qanda', 'explainer_image') and data is not None:
            payload['data'] = data
        else:
            payload['content'] = content

        return Response(payload, status=status.HTTP_200_OK)


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
        
        # Delete image and thumbnail from GCS if it's an image block
        if block.block_type == 'image' and block.content:
            try:
                from urllib.parse import urlparse, unquote
                parsed_url = urlparse(block.content)
                path_parts = parsed_url.path.strip('/').split('/', 1)
                if len(path_parts) > 1:
                    file_path = unquote(path_parts[1])
                else:
                    file_path = unquote(parsed_url.path.strip('/'))
                
                # Delete both main image and thumbnail
                main_deleted, thumb_deleted = delete_image_and_thumbnail(file_path)
                if main_deleted or thumb_deleted:
                    logger.info(f"✅ Deleted image and thumbnail from GCS when deleting block: {file_path}")
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

            file_path = file_path_from_tutorx_image_url(image_url)
            if not file_path:
                return Response(
                    {'error': 'Invalid or unsupported image_url'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            logger.info("Deleting TutorX image and thumbnail from GCS: %s (from URL: %s)", file_path, image_url[:80])
            main_deleted, thumb_deleted = delete_image_and_thumbnail(file_path)
            if main_deleted or thumb_deleted:
                messages = []
                if main_deleted:
                    messages.append("main image")
                if thumb_deleted:
                    messages.append("thumbnail")
                message = f"Successfully deleted {', '.join(messages)}"
                logger.info("✅ %s", message)
                return Response(
                    {'message': message},
                    status=status.HTTP_200_OK
                )
            logger.warning("TutorX image file not found in GCS: %s", file_path)
            return Response(
                {'message': 'Image file not found (may have already been deleted)'},
                status=status.HTTP_200_OK
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
