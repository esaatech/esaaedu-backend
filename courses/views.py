from django.shortcuts import get_object_or_404
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .models import Course, Lesson, Quiz, Question
from .serializers import (
    CourseListSerializer, CourseDetailSerializer, CourseCreateUpdateSerializer,
    FrontendCourseSerializer, FeaturedCoursesSerializer
)


class CoursesPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 50


# ===== PUBLIC ENDPOINTS (for frontend/students) =====

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def featured_courses(request):
    """
    Get featured courses for home page
    """
    try:
        serializer = FeaturedCoursesSerializer({})
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': 'Failed to fetch featured courses', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def public_courses_list(request):
    """
    Get all published courses for public viewing
    """
    try:
        courses = Course.objects.filter(status='published').order_by('-featured', '-created_at')
        
        # Apply pagination
        paginator = CoursesPagination()
        page = paginator.paginate_queryset(courses, request)
        
        if page is not None:
            serializer = FrontendCourseSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = FrontendCourseSerializer(courses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Failed to fetch courses', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ===== TEACHER ENDPOINTS =====

@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def teacher_courses(request):
    """
    GET: List all courses created by the authenticated teacher
    POST: Create a new course
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        try:
            courses = Course.objects.filter(teacher=request.user).order_by('-created_at')
            serializer = CourseListSerializer(courses, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch courses', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'POST':
        try:
            serializer = CourseCreateUpdateSerializer(data=request.data)
            if serializer.is_valid():
                course = serializer.save(teacher=request.user)
                response_serializer = CourseDetailSerializer(course)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': 'Failed to create course', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
