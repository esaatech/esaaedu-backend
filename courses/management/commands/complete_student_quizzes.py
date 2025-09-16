from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from courses.models import Course, Lesson, Quiz, Question, QuizAttempt
from student.models import EnrolledCourse
import json
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Complete quizzes for specified students to generate test data for teacher grading'

    def add_arguments(self, parser):
        parser.add_argument(
            '--students',
            nargs='+',
            default=['engrjoelivon@yahoo.com', 'efrefre@yahoo.com'],
            help='Email addresses of students to complete quizzes for'
        )
        parser.add_argument(
            '--course',
            type=str,
            default='Android',
            help='Course name to complete quizzes for (default: Android)'
        )

    def handle(self, *args, **options):
        student_emails = options['students']
        course_name = options['course']

        self.stdout.write(
            self.style.SUCCESS(f'Starting quiz completion for students: {", ".join(student_emails)}')
        )

        # Find the course
        try:
            course = Course.objects.filter(title__icontains=course_name).first()
            if not course:
                self.stdout.write(
                    self.style.ERROR(f'Course containing "{course_name}" not found')
                )
                return
            
            self.stdout.write(f'Found course: {course.title}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error finding course: {str(e)}'))
            return

        # Process each student
        for email in student_emails:
            try:
                self.complete_quizzes_for_student(email, course)
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error processing student {email}: {str(e)}')
                )

        self.stdout.write(
            self.style.SUCCESS('Quiz completion process finished!')
        )

    def complete_quizzes_for_student(self, email, course):
        # Find the student
        try:
            student = User.objects.get(email=email, role='student')
            self.stdout.write(f'Found student: {student.get_full_name()} ({email})')
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Student with email {email} not found')
            )
            return

        # Check if student is enrolled in the course
        try:
            # Get student profile first
            student_profile = student.student_profile
            enrollment = EnrolledCourse.objects.get(
                student_profile=student_profile,
                course=course,
                status='active'
            )
            self.stdout.write(f'Student is enrolled in {course.title}')
        except (EnrolledCourse.DoesNotExist, AttributeError):
            self.stdout.write(
                self.style.WARNING(f'Student {email} is not enrolled in {course.title}')
            )
            return

        # Get all lessons with quizzes for this course
        lessons_with_quizzes = Lesson.objects.filter(
            course=course,
            quiz__isnull=False
        ).select_related('quiz')

        if not lessons_with_quizzes.exists():
            self.stdout.write(
                self.style.WARNING(f'No lessons with quizzes found for course {course.title}')
            )
            return

        self.stdout.write(f'Found {lessons_with_quizzes.count()} lessons with quizzes')

        # Complete quizzes for each lesson
        for lesson in lessons_with_quizzes:
            try:
                self.complete_quiz_for_lesson(student, lesson, enrollment)
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error completing quiz for lesson {lesson.title}: {str(e)}')
                )

    def complete_quiz_for_lesson(self, student, lesson, enrollment):
        quiz = lesson.quiz
        
        # Check if student already has a completed attempt for this quiz
        existing_attempt = QuizAttempt.objects.filter(
            student=student,
            quiz=quiz,
            completed_at__isnull=False
        ).first()

        if existing_attempt:
            self.stdout.write(
                self.style.WARNING(f'Student already completed quiz: {quiz.title}')
            )
            return

        # Get all questions for this quiz
        questions = Question.objects.filter(quiz=quiz).order_by('order')
        if not questions.exists():
            self.stdout.write(
                self.style.WARNING(f'No questions found for quiz: {quiz.title}')
            )
            return

        # Generate realistic student answers
        student_answers = {}
        total_points = 0
        earned_points = 0

        for question in questions:
            total_points += question.points
            answer, is_correct = self.generate_student_answer(question)
            student_answers[str(question.id)] = answer
            
            if is_correct:
                earned_points += question.points

        # Calculate score
        score_percentage = (earned_points / total_points * 100) if total_points > 0 else 0
        passed = score_percentage >= quiz.passing_score

        # Create the quiz attempt
        started_time = timezone.now() - timezone.timedelta(minutes=random.randint(15, 45))
        completed_time = timezone.now()

        quiz_attempt = QuizAttempt.objects.create(
            student=student,
            quiz=quiz,
            enrollment=enrollment,
            attempt_number=1,
            started_at=started_time,
            completed_at=completed_time,
            score=score_percentage,
            points_earned=earned_points,
            passed=passed,
            answers=student_answers
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Completed quiz "{quiz.title}" for {student.get_full_name()} '
                f'- Score: {score_percentage:.1f}% ({earned_points}/{total_points} points)'
            )
        )

        return quiz_attempt

    def generate_student_answer(self, question):
        """Generate a realistic student answer based on question type"""
        
        # Get content from the JSONField
        content = question.content or {}
        
        if question.type == 'multiple_choice':
            options = content.get('options', [])
            correct_answer = content.get('correct_answer', '')
            
            if not options or not correct_answer:
                return "No answer", False
            
            # 70% chance of getting it right
            if random.random() < 0.7:
                return correct_answer, True
            else:
                # Pick a wrong answer
                wrong_options = [opt for opt in options if opt != correct_answer]
                return random.choice(wrong_options) if wrong_options else options[0], False

        elif question.type == 'true_false':
            correct_answer = content.get('correct_answer', 'true')
            
            # 75% chance of getting it right
            if random.random() < 0.75:
                return correct_answer, True
            else:
                return 'false' if correct_answer == 'true' else 'true', False

        elif question.type == 'short_answer':
            correct_answer = content.get('correct_answer', 'Sample answer')
            
            # 60% chance of getting it right
            if random.random() < 0.6:
                # Return correct answer with slight variations
                variations = [
                    correct_answer,
                    correct_answer.lower(),
                    correct_answer.capitalize()
                ]
                return random.choice(variations), True
            else:
                # Generate plausible wrong answers
                wrong_answers = [
                    "I'm not sure about this",
                    "Need to study more",
                    "Similar concept but different",
                    "Partially correct but incomplete"
                ]
                return random.choice(wrong_answers), False

        elif question.type == 'fill_blank':
            correct_answer = content.get('correct_answer', 'answer')
            
            # 65% chance of getting it right
            if random.random() < 0.65:
                return correct_answer, True
            else:
                # Common wrong answers for fill-in-the-blank
                wrong_answers = ['function', 'method', 'variable', 'class', 'object', 'component']
                return random.choice(wrong_answers), False

        elif question.type == 'essay':
            correct_answer = content.get('correct_answer', 'Sample essay answer')
            
            # 55% chance of getting it right (essays are harder)
            if random.random() < 0.55:
                # Generate a decent answer based on the correct answer
                good_answers = [
                    f"This relates to {correct_answer[:50]}... and involves multiple concepts that work together to create effective solutions.",
                    f"From my understanding, {correct_answer[:40]}... which is important because it helps solve real-world problems in development.",
                    f"The key concepts include: {correct_answer[:60]}... This demonstrates the relationship between different programming elements."
                ]
                return random.choice(good_answers), True
            else:
                # Generate a weak answer
                weak_answers = [
                    "I think this has something to do with programming concepts but I'm not entirely sure of the specific details.",
                    "This is related to what we learned in class but I need to review the material more thoroughly.",
                    "I remember discussing this topic but I can't recall the exact implementation details right now."
                ]
                return random.choice(weak_answers), False

        elif question.type == 'matching':
            # Handle matching questions
            pairs = content.get('pairs', [])
            if not pairs:
                return [], False
                
            # 60% chance of getting most matches right
            student_pairs = []
            for pair in pairs:
                if random.random() < 0.6:
                    student_pairs.append(pair)  # Correct match
                else:
                    # Create wrong match
                    other_pairs = [p for p in pairs if p != pair]
                    if other_pairs:
                        wrong_pair = {
                            'left': pair['left'],
                            'right': random.choice(other_pairs)['right']
                        }
                        student_pairs.append(wrong_pair)
                    else:
                        student_pairs.append(pair)
            
            # Check if mostly correct
            correct_count = sum(1 for sp in student_pairs if sp in pairs)
            is_correct = correct_count >= len(pairs) * 0.6
            
            return student_pairs, is_correct

        elif question.type == 'ordering':
            # Handle ordering questions
            items = content.get('items', [])
            correct_order = content.get('correct_order', items)
            
            if not items:
                return [], False
                
            # 50% chance of getting order mostly right
            if random.random() < 0.5:
                return correct_order, True
            else:
                # Shuffle the order slightly
                shuffled = items.copy()
                random.shuffle(shuffled)
                return shuffled, False

        # Default fallback
        return "No answer provided", False
