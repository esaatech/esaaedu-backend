from django.shortcuts import get_object_or_404
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .models import EnrolledCourse
from .serializers import (
    EnrolledCourseListSerializer, 
    EnrolledCourseDetailSerializer, 
    EnrolledCourseCreateUpdateSerializer
)


class StudentPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def enrolled_courses(request):
    """
    GET: List enrolled courses (filtered by user role)
    POST: Create new enrollment (teachers/admins only)
    """
    if request.method == 'GET':
        try:
            # Filter based on user role
            if request.user.role == 'student':
                enrollments = EnrolledCourse.objects.filter(
                    student_profile__user=request.user
                ).order_by('-enrollment_date')
            elif request.user.role == 'teacher':
                enrollments = EnrolledCourse.objects.filter(
                    course__teacher=request.user
                ).order_by('-enrollment_date')
            else:
                enrollments = EnrolledCourse.objects.all().order_by('-enrollment_date')
            
            paginator = StudentPagination()
            page = paginator.paginate_queryset(enrollments, request)
            
            if page is not None:
                serializer = EnrolledCourseListSerializer(page, many=True)
                return paginator.get_paginated_response(serializer.data)
            
            serializer = EnrolledCourseListSerializer(enrollments, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch enrolled courses', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'POST':
        if request.user.role not in ['teacher', 'admin']:
            return Response(
                {'error': 'Only teachers and admins can create enrollments'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            serializer = EnrolledCourseCreateUpdateSerializer(
                data=request.data,
                context={'request': request}
            )
            if serializer.is_valid():
                enrollment = serializer.save(enrolled_by=request.user)
                response_serializer = EnrolledCourseDetailSerializer(enrollment)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': 'Failed to create enrollment', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def enrolled_course_detail(request, enrollment_id):
    """
    GET: Retrieve enrollment details
    PUT: Update enrollment
    DELETE: Delete enrollment
    """
    try:
        if request.user.role == 'student':
            enrollment = get_object_or_404(
                EnrolledCourse, 
                id=enrollment_id, 
                student_profile__user=request.user
            )
        elif request.user.role == 'teacher':
            enrollment = get_object_or_404(
                EnrolledCourse, 
                id=enrollment_id, 
                course__teacher=request.user
            )
        else:
            enrollment = get_object_or_404(EnrolledCourse, id=enrollment_id)
    except Exception:
        return Response(
            {'error': 'Enrollment not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        try:
            serializer = EnrolledCourseDetailSerializer(enrollment)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch enrollment details', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'PUT':
        if request.user.role not in ['teacher', 'admin']:
            return Response(
                {'error': 'Only teachers and admins can update enrollments'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            serializer = EnrolledCourseCreateUpdateSerializer(
                enrollment, 
                data=request.data, 
                context={'request': request},
                partial=True
            )
            if serializer.is_valid():
                updated_enrollment = serializer.save()
                response_serializer = EnrolledCourseDetailSerializer(updated_enrollment)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': 'Failed to update enrollment', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    elif request.method == 'DELETE':
        if request.user.role not in ['teacher', 'admin']:
            return Response(
                {'error': 'Only teachers and admins can delete enrollments'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            enrollment.delete()
            return Response(
                {'message': 'Enrollment deleted successfully'},
                status=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            return Response(
                {'error': 'Failed to delete enrollment', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
