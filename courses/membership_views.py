"""
Course co-teacher membership list / add / remove APIs.
"""
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import Course, CourseMembership
from .permissions import user_is_course_member, user_is_course_owner, ensure_owner_membership
from .serializers import _serialize_course_teachers

User = get_user_model()


@api_view(['GET', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def course_teachers(request, course_id):
    """
    GET: List owner + co-teachers (any course member)
    POST: Add a co-teacher by user_id or email (owner only)
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN,
        )

    course = get_object_or_404(Course.objects.select_related('teacher'), id=course_id)
    ensure_owner_membership(course)

    if request.method == 'GET':
        if not user_is_course_member(request.user, course):
            return Response(
                {'error': 'You do not have permission to view teachers for this course'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            {
                'teachers': _serialize_course_teachers(course),
                'my_role': 'owner' if user_is_course_owner(request.user, course) else 'teacher',
            },
            status=status.HTTP_200_OK,
        )

    # POST — owner only
    if not user_is_course_owner(request.user, course):
        return Response(
            {'error': 'Only the course owner can add co-teachers'},
            status=status.HTTP_403_FORBIDDEN,
        )

    user_id = request.data.get('user_id')
    email = (request.data.get('email') or '').strip().lower()

    if not user_id and not email:
        return Response(
            {'error': 'Provide user_id or email of an existing teacher'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        if user_id is not None:
            teacher = User.objects.get(id=user_id)
        else:
            teacher = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        return Response(
            {'error': 'Teacher not found. They must already have a teacher account.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    except (TypeError, ValueError):
        return Response(
            {'error': 'Invalid user_id'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if teacher.role != 'teacher':
        return Response(
            {'error': 'Only users with the teacher role can be added as co-teachers'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if teacher.id == course.teacher_id:
        return Response(
            {'error': 'This user is already the course owner'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    membership, created = CourseMembership.objects.get_or_create(
        course=course,
        user=teacher,
        defaults={
            'role': CourseMembership.ROLE_TEACHER,
            'invited_by': request.user,
        },
    )
    if not created:
        return Response(
            {'error': 'This teacher is already a member of the course'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {
            'message': 'Co-teacher added',
            'teachers': _serialize_course_teachers(course),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def course_teacher_detail(request, course_id, user_id):
    """
    DELETE: Remove a co-teacher (owner only). Cannot remove the owner.
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN,
        )

    course = get_object_or_404(Course, id=course_id)

    if not user_is_course_owner(request.user, course):
        return Response(
            {'error': 'Only the course owner can remove co-teachers'},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        return Response({'error': 'Invalid user_id'}, status=status.HTTP_400_BAD_REQUEST)

    if user_id_int == course.teacher_id:
        return Response(
            {'error': 'Cannot remove the course owner'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    deleted, _ = CourseMembership.objects.filter(
        course=course,
        user_id=user_id_int,
        role=CourseMembership.ROLE_TEACHER,
    ).delete()

    if not deleted:
        return Response(
            {'error': 'Co-teacher not found on this course'},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        {
            'message': 'Co-teacher removed',
            'teachers': _serialize_course_teachers(course),
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def search_teachers(request):
    """
    GET: Search existing teachers by email or name (for invite UI).
    Query: ?q=...
    """
    if request.user.role != 'teacher':
        return Response(
            {'error': 'Only teachers can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN,
        )

    q = (request.query_params.get('q') or '').strip()
    if len(q) < 2:
        return Response({'teachers': []}, status=status.HTTP_200_OK)

    teachers = User.objects.filter(role='teacher').exclude(id=request.user.id)
    if '@' in q:
        teachers = teachers.filter(email__icontains=q)
    else:
        from django.db.models import Q
        teachers = teachers.filter(
            Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )

    results = [
        {
            'id': t.id,
            'name': t.get_full_name() or t.email,
            'email': t.email,
        }
        for t in teachers.order_by('first_name', 'last_name')[:20]
    ]
    return Response({'teachers': results}, status=status.HTTP_200_OK)
