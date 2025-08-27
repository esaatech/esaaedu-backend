from django.utils import timezone
from django.db.models import Q
from .models import Lesson, Quiz, Question, QuizAttempt, ClassEvent, LessonMaterial
from student.models import EnrolledCourse
from datetime import datetime, timedelta


class StudentLessonService:
    """
    Service class to handle consolidated lesson data fetching for students
    Combines lesson, quiz, class events, and attempt information
    """
    
    @staticmethod
    def get_comprehensive_lesson_data(lesson_id, student_profile):
        """
        Get comprehensive lesson data including quiz, class events, and attempt information
        """
        try:
            # Get the lesson
            lesson = Lesson.objects.select_related('course').get(id=lesson_id)
            
            # Get enrollment
            enrollment = EnrolledCourse.objects.filter(
                student_profile=student_profile,
                course=lesson.course,
                status__in=['active', 'completed']
            ).first()
            
            if not enrollment:
                return None, "Student not enrolled in this course"
            
            # Get quiz data with questions
            quiz_data = StudentLessonService._get_quiz_data(lesson, student_profile)
            
            # Get class event data (for live lessons)
            class_event_data = StudentLessonService._get_class_event_data(lesson)
            
            # Get lesson progress/status
            lesson_status = StudentLessonService._get_lesson_status(lesson, enrollment)

            # Get lesson materials
            lesson_materials = StudentLessonService._get_lesson_materials(lesson)
            
            # Build comprehensive response
            lesson_data = {
                # Basic lesson info
                'id': str(lesson.id),
                'title': lesson.title,
                'description': lesson.description or '',
                'type': lesson.type,
                'duration': lesson.duration,
                'order': lesson.order,
                'text_content': lesson.text_content or '',
                'video_url': lesson.video_url or '',
                'audio_url': lesson.audio_url or '',
                
                'prerequisites': list(lesson.prerequisites.values_list('id', flat=True)) if lesson.prerequisites.exists() else [],
                
                # Course info
                'course_id': str(lesson.course.id),
                'course_title': lesson.course.title,
                'teacher_name': lesson.course.teacher.get_full_name() or lesson.course.teacher.email,
                
                # Lesson materials
                'materials': lesson_materials,

                # Lesson status
                'status': lesson_status,
                
                # Quiz data (if exists)
                'quiz': quiz_data,
                
                # Class event data (for live lessons)
                'class_event': class_event_data,
                
                # Enrollment info
                'enrollment_status': enrollment.status,
                'progress_percentage': float(enrollment.progress_percentage),
            }
            
            return lesson_data, None
            
        except Lesson.DoesNotExist:
            return None, "Lesson not found"
        except Exception as e:
            return None, f"Error fetching lesson data: {str(e)}"
    
    @staticmethod
    def _get_quiz_data(lesson, student_profile):
        """
        Get quiz data including questions and student attempts
        """
        try:
            quiz = Quiz.objects.get(lesson=lesson)
            questions = quiz.questions.all().order_by('order')
            
            # Get student's attempts for this quiz
            attempts = QuizAttempt.objects.filter(
                student=student_profile.user,
                quiz=quiz
            ).order_by('-attempt_number')
            
            # Calculate attempt statistics
            total_attempts = attempts.count()
            last_attempt = attempts.first() if attempts.exists() else None
            can_retake = total_attempts < quiz.max_attempts
            has_passed = last_attempt.passed if last_attempt else False
            
            quiz_data = {
                'id': str(quiz.id),
                'title': quiz.title,
                'description': quiz.description or '',
                'time_limit': quiz.time_limit,
                'passing_score': quiz.passing_score,
                'max_attempts': quiz.max_attempts,
                'show_correct_answers': quiz.show_correct_answers,
                'randomize_questions': quiz.randomize_questions,
                'total_points': quiz.total_points,
                'question_count': quiz.question_count,
                
                # Student-specific data
                'user_attempts_count': total_attempts,
                'can_retake': can_retake,
                'has_passed': has_passed,
                'last_attempt': last_attempt.score if last_attempt else None,
                'last_attempt_passed': last_attempt.passed if last_attempt else None,
                
                # Questions
                'questions': [
                    {
                        'id': str(q.id),
                        'question_text': q.question_text.split('\n')[0].strip(),  # Clean question text
                        'order': q.order,
                        'points': q.points,
                        'type': q.type,
                        'content': q.content,
                        'explanation': q.explanation or ''
                    }
                    for q in questions
                ]
            }
            
            return quiz_data
            
        except Quiz.DoesNotExist:
            return None
        except Exception as e:
            print(f"Error getting quiz data: {e}")
            return None
    
    @staticmethod
    def _get_class_event_data(lesson):
        """
        Get class event data for live lessons
        """
        if lesson.type != 'live_class':
            return None
            
        try:
            # Find class event for this lesson
            class_event = ClassEvent.objects.filter(
                lesson=lesson,
                event_type='lesson'
            ).first()
            
            if not class_event:
                return None
            
            # Calculate current status
            now = timezone.now()
            start_time = class_event.start_time
            end_time = class_event.end_time
            
            # Determine if class is ongoing, upcoming, or past
            if now < start_time:
                status = 'upcoming'
                time_until_start = (start_time - now).total_seconds()
                can_join_early = time_until_start <= 15 * 60  # 15 minutes before
            elif start_time <= now <= end_time:
                status = 'ongoing'
                can_join_early = True
            else:
                status = 'completed'
                can_join_early = False
            
            event_data = {
                'id': str(class_event.id),
                'title': class_event.title,
                'description': class_event.description or '',
                'start_time': start_time,
                'end_time': end_time,
                'meeting_platform': class_event.meeting_platform or 'google-meet',
                'meeting_link': class_event.meeting_link or '',
                'meeting_id': class_event.meeting_id or '',
                
                # Calculated status
                'status': status,
                'can_join_early': can_join_early,
                'is_live_now': status == 'ongoing',
                'time_until_start': (start_time - now).total_seconds() if status == 'upcoming' else None,
                'duration_minutes': int((end_time - start_time).total_seconds() / 60) if end_time and start_time else 0,
            }
            
            return event_data
            
        except Exception as e:
            print(f"Error getting class event data: {e}")
            return None
    
    @staticmethod
    def _get_lesson_status(lesson, enrollment):
        """
        Determine lesson status based on enrollment and progress
        """
        # For now, implement basic logic
        # TODO: Implement proper lesson progress tracking when LessonProgress model is created
        
        if lesson.order == 1:
            return 'current'
        else:
            # Check if previous lesson is completed
            previous_lesson = Lesson.objects.filter(
                course=lesson.course,
                order=lesson.order - 1
            ).first()
            
            if previous_lesson:
                # TODO: Check if previous lesson is completed in enrollment
                # For now, return locked
                return 'locked'
            else:
                return 'locked'
    
    @staticmethod
    def get_course_lessons_with_progress(course_id, student_profile):
        """
        Get all lessons for a course with progress information
        """
        try:
            from .models import Course
            
            course = Course.objects.get(id=course_id)
            lessons = Lesson.objects.filter(course=course).order_by('order')
            
            # Get enrollment
            enrollment = EnrolledCourse.objects.filter(
                student_profile=student_profile,
                course=course,
                status__in=['active', 'completed']
            ).first()
            
            if not enrollment:
                return None, "Student not enrolled in this course"
            
            lessons_data = []
            for lesson in lessons:
                # Get basic quiz info (without questions for performance)
                quiz_basic = None
                try:
                    quiz = Quiz.objects.get(lesson=lesson)
                    attempts = QuizAttempt.objects.filter(
                        student=student_profile.user,
                        quiz=quiz
                    )
                    
                    quiz_basic = {
                        'id': str(quiz.id),
                        'title': quiz.title,
                        'has_quiz': True,
                        'attempts_count': attempts.count(),
                        'max_attempts': quiz.max_attempts,
                        'has_passed': attempts.filter(passed=True).exists(),
                    }
                except Quiz.DoesNotExist:
                    quiz_basic = {'has_quiz': False}
                
                lesson_data = {
                    'id': str(lesson.id),
                    'title': lesson.title,
                    'description': lesson.description or '',
                    'type': lesson.type,
                    'duration': lesson.duration,
                    'order': lesson.order,
                    'status': StudentLessonService._get_lesson_status(lesson, enrollment),
                    'quiz': quiz_basic,
                }
                
                lessons_data.append(lesson_data)
            
            return {
                'course_id': str(course.id),
                'course_title': course.title,
                'lessons': lessons_data,
                'total_lessons': len(lessons_data),
                'enrollment_status': enrollment.status,
                'progress_percentage': float(enrollment.progress_percentage),
            }, None
            
        except Course.DoesNotExist:
            return None, "Course not found"
        except Exception as e:
            return None, f"Error fetching course lessons: {str(e)}"

    @staticmethod
    def get_course_materials_summary(course_id, student_profile):
        """
        Get a summary of all materials across all lessons in a course
        Useful for showing what materials are available before starting
        """
        try:
            from .models import Course
            
            course = Course.objects.get(id=course_id)
            lessons = Lesson.objects.filter(course=course).order_by('order')
            
            # Get enrollment
            enrollment = EnrolledCourse.objects.filter(
                student_profile=student_profile,
                course=course,
                status__in=['active', 'completed']
            ).first()
            
            if not enrollment:
                return None, "Student not enrolled in this course"
            
            materials_summary = []
            for lesson in lessons:
                lesson_materials = StudentLessonService._get_lesson_materials(lesson)
                if lesson_materials:
                    materials_summary.append({
                        'lesson_id': str(lesson.id),
                        'lesson_title': lesson.title,
                        'lesson_order': lesson.order,
                        'materials': lesson_materials,
                        'required_materials_count': len([m for m in lesson_materials if m['is_required']]),
                        'total_materials_count': len(lesson_materials),
                    })
            
            return {
                'course_id': str(course.id),
                'course_title': course.title,
                'materials_summary': materials_summary,
                'total_lessons_with_materials': len(materials_summary),
                'total_materials': sum(len(ms['materials']) for ms in materials_summary),
                'total_required_materials': sum(ms['required_materials_count'] for ms in materials_summary),
            }, None
            
        except Course.DoesNotExist:
            return None, "Course not found"
        except Exception as e:
            return None, f"Error fetching course materials summary: {str(e)}"

    @staticmethod
    def _get_lesson_materials(lesson):
        """
        Get lesson materials for a specific lesson
        Returns serialized material data
        """
        try:
            materials = LessonMaterial.objects.filter(lesson=lesson).order_by('order')
            
            materials_data = []
            for material in materials:
                material_data = {
                    'id': str(material.id),
                    'title': material.title,
                    'description': material.description or '',
                    'material_type': material.material_type,
                    'file_url': material.file_url or '',
                    'file_size': material.file_size,
                    'file_size_mb': material.file_size_mb,
                    'file_extension': material.file_extension or '',
                    'is_required': material.is_required,
                    'is_downloadable': material.is_downloadable,
                    'order': material.order,
                    'created_at': material.created_at.isoformat() if material.created_at else None,
                }
                materials_data.append(material_data)
            
            return materials_data
            
        except Exception as e:
            # Log error but don't fail the entire lesson fetch
            print(f"Error fetching lesson materials for lesson {lesson.id}: {str(e)}")
            return []
