"""
Health check endpoints for monitoring system health
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import connection
from student.models import EnrolledCourse
from courses.models import Assignment, AssignmentSubmission
import logging

logger = logging.getLogger('assignment_submission')

@require_http_methods(["GET"])
def health_check(request):
    """Basic health check endpoint"""
    try:
        # Test database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        return JsonResponse({
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'database': 'connected'
        })
    except Exception as e:
        logger.error("Health check failed", extra={'error': str(e)})
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)

@require_http_methods(["GET"])
def enrollment_health_check(request):
    """Check enrollment system health"""
    try:
        # Test enrollment queries
        active_enrollments = EnrolledCourse.objects.filter(status='active').count()
        completed_enrollments = EnrolledCourse.objects.filter(status='completed').count()
        
        # Test assignment submission queries
        total_assignments = Assignment.objects.count()
        total_submissions = AssignmentSubmission.objects.count()
        
        return JsonResponse({
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'enrollments': {
                'active': active_enrollments,
                'completed': completed_enrollments,
                'total': active_enrollments + completed_enrollments
            },
            'assignments': {
                'total': total_assignments,
                'submissions': total_submissions
            }
        })
    except Exception as e:
        logger.error("Enrollment health check failed", extra={'error': str(e)})
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)

@require_http_methods(["GET"])
def assignment_submission_stats(request):
    """Get assignment submission statistics for monitoring"""
    try:
        from django.db.models import Count
        
        # Get submission stats by status
        status_stats = AssignmentSubmission.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        # Get submission stats by enrollment status
        enrollment_stats = AssignmentSubmission.objects.select_related(
            'enrollment'
        ).values('enrollment__status').annotate(
            count=Count('id')
        ).order_by('enrollment__status')
        
        return JsonResponse({
            'status': 'success',
            'timestamp': timezone.now().isoformat(),
            'submission_stats': {
                'by_status': list(status_stats),
                'by_enrollment_status': list(enrollment_stats)
            }
        })
    except Exception as e:
        logger.error("Assignment stats check failed", extra={'error': str(e)})
        return JsonResponse({
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=500)
