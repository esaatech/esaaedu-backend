from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from courses.models import Course, Lesson, Quiz, Question, CourseEnrollment, LessonProgress, QuizAttempt

User = get_user_model()


class Command(BaseCommand):
    help = 'Clear all sample course data'

    def handle(self, *args, **options):
        self.stdout.write('Clearing sample course data...')
        
        # Delete in reverse order of dependencies
        deleted_counts = {}
        
        # Delete quiz attempts
        count = QuizAttempt.objects.all().count()
        QuizAttempt.objects.all().delete()
        deleted_counts['Quiz Attempts'] = count
        
        # Delete lesson progress
        count = LessonProgress.objects.all().count()
        LessonProgress.objects.all().delete()
        deleted_counts['Lesson Progress'] = count
        
        # Delete course enrollments
        count = CourseEnrollment.objects.all().count()
        CourseEnrollment.objects.all().delete()
        deleted_counts['Course Enrollments'] = count
        
        # Delete questions
        count = Question.objects.all().count()
        Question.objects.all().delete()
        deleted_counts['Questions'] = count
        
        # Delete quizzes
        count = Quiz.objects.all().count()
        Quiz.objects.all().delete()
        deleted_counts['Quizzes'] = count
        
        # Delete lessons
        count = Lesson.objects.all().count()
        Lesson.objects.all().delete()
        deleted_counts['Lessons'] = count
        
        # Delete courses
        count = Course.objects.all().count()
        Course.objects.all().delete()
        deleted_counts['Courses'] = count
        
        # Optionally delete the sample teacher user
        sample_teacher = User.objects.filter(email='teacher@example.com').first()
        if sample_teacher:
            sample_teacher.delete()
            deleted_counts['Sample Teacher'] = 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n🧹 Successfully cleared sample data!\n'
            )
        )
        
        for item_type, count in deleted_counts.items():
            if count > 0:
                self.stdout.write(f'  ✅ Deleted {count} {item_type}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n📊 Database is now clean for new teachers to start fresh!'
            )
        )
