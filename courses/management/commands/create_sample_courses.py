from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from courses.models import Course, Lesson, Quiz, Question

User = get_user_model()


class Command(BaseCommand):
    help = 'Create sample courses for testing'

    def handle(self, *args, **options):
        self.stdout.write('Creating sample courses...')
        
        # Get or create a teacher user
        teacher, created = User.objects.get_or_create(
            email='teacher@example.com',
            defaults={
                'first_name': 'Sarah',
                'last_name': 'Johnson',
                'role': 'teacher',
                'firebase_uid': 'sample_teacher_uid'
            }
        )
        
        if created:
            self.stdout.write(f'Created teacher user: {teacher.email}')
        else:
            self.stdout.write(f'Using existing teacher: {teacher.email}')
        
        # Sample course data matching the frontend structure
        sample_courses = [
            {
                'title': 'Scratch Programming for Kids',
                'description': 'Learn to code with colorful blocks! Perfect for beginners aged 6-10.',
                'long_description': 'Start your coding journey with Scratch, a visual programming language designed specifically for kids. Create interactive stories, games, and animations while learning fundamental programming concepts like loops, conditionals, and variables.',
                'category': 'Programming',
                'age_range': 'Ages 6-10',
                'duration': '8 weeks',
                'level': 'beginner',
                'price': 199.00,
                'features': ['Visual block-based coding', 'Interactive storytelling', 'Game creation', 'Animation basics', 'Problem-solving skills'],
                'featured': True,
                'popular': False,
                'color': 'bg-gradient-primary',
                'icon': 'Code',
                'max_students': 8,
                'schedule': '2 sessions per week',
                'certificate': True,
                'status': 'published',
                'lessons': [
                    {
                        'title': 'Getting Started with Scratch',
                        'description': 'Introduction to Scratch interface and basic concepts',
                        'order': 1,
                        'duration': 45,
                        'type': 'live',
                        'content': {
                            'platform': 'zoom',
                            'meeting_url': 'https://zoom.us/j/123456789',
                            'meeting_id': '123 456 789',
                            'meeting_password': 'scratch123'
                        }
                    },
                    {
                        'title': 'Creating Your First Animation',
                        'description': 'Learn to animate sprites and create simple movements',
                        'order': 2,
                        'duration': 60,
                        'type': 'recorded',
                        'content': {
                            'video_url': 'https://example.com/video/animation-basics',
                            'video_duration': 60,
                            'transcript': 'Available'
                        }
                    }
                ]
            },
            {
                'title': 'Web Development Fundamentals',
                'description': 'Build real websites and learn HTML, CSS, and JavaScript basics.',
                'long_description': 'Create your own websites from scratch! Learn the building blocks of the web including HTML for structure, CSS for styling, and JavaScript for interactivity. Build a personal portfolio website you can share with friends and family.',
                'category': 'Web Development',
                'age_range': 'Ages 10-14',
                'duration': '12 weeks',
                'level': 'intermediate',
                'price': 299.00,
                'features': ['HTML & CSS mastery', 'JavaScript basics', 'Responsive design', 'Portfolio creation', 'Web hosting'],
                'featured': True,
                'popular': True,
                'color': 'bg-gradient-to-br from-blue-500 to-cyan-600',
                'icon': 'Laptop',
                'max_students': 8,
                'schedule': '2 sessions per week',
                'certificate': True,
                'status': 'published',
                'lessons': [
                    {
                        'title': 'HTML Basics',
                        'description': 'Learn the structure of web pages with HTML',
                        'order': 1,
                        'duration': 50,
                        'type': 'material',
                        'content': {
                            'reading_materials': ['HTML Guide PDF', 'Interactive HTML Tutorial'],
                            'estimated_reading_time': 30
                        }
                    }
                ]
            },
            {
                'title': 'Python Programming for Beginners',
                'description': 'Learn real programming with Python! Perfect for older kids ready for text-based coding.',
                'long_description': 'Take the next step in programming with Python! Learn text-based coding, work with data, create simple programs, and understand computer science fundamentals. Great preparation for advanced programming.',
                'category': 'Programming',
                'age_range': 'Ages 12-16',
                'duration': '12 weeks',
                'level': 'advanced',
                'price': 329.00,
                'features': ['Text-based coding', 'Data structures', 'Algorithm basics', 'Project building', 'CS fundamentals'],
                'featured': False,
                'popular': False,
                'color': 'bg-gradient-to-br from-yellow-500 to-orange-600',
                'icon': 'Code',
                'max_students': 6,
                'schedule': '2 sessions per week',
                'certificate': True,
                'status': 'draft',
                'lessons': []
            }
        ]
        
        created_courses = []
        
        for course_data in sample_courses:
            lessons_data = course_data.pop('lessons', [])
            
            # Create course
            course, created = Course.objects.get_or_create(
                title=course_data['title'],
                teacher=teacher,
                defaults=course_data
            )
            
            if created:
                self.stdout.write(f'✅ Created course: {course.title}')
                
                # Create lessons for the course
                for lesson_data in lessons_data:
                    lesson = Lesson.objects.create(
                        course=course,
                        **lesson_data
                    )
                    self.stdout.write(f'  📚 Added lesson: {lesson.title}')
                    
                    # Add a sample quiz to the first lesson
                    if lesson.order == 1:
                        quiz = Quiz.objects.create(
                            lesson=lesson,
                            title=f'{lesson.title} Quiz',
                            description='Test your understanding of this lesson',
                            passing_score=70,
                            max_attempts=3,
                            show_correct_answers=True
                        )
                        
                        # Add sample questions
                        questions = [
                            {
                                'question_text': 'What is the main purpose of Scratch programming?',
                                'order': 1,
                                'points': 1,
                                'type': 'multiple_choice',
                                'content': {
                                    'options': [
                                        'To create complex business applications',
                                        'To teach programming concepts through visual blocks',
                                        'To build mobile apps',
                                        'To design websites'
                                    ],
                                    'correct_answer': 1
                                },
                                'explanation': 'Scratch is designed to teach programming concepts using visual blocks, making it perfect for beginners.'
                            },
                            {
                                'question_text': 'Scratch uses visual blocks instead of text-based code.',
                                'order': 2,
                                'points': 1,
                                'type': 'true_false',
                                'content': {
                                    'correct_answer': True
                                },
                                'explanation': 'Yes! Scratch uses colorful, drag-and-drop blocks instead of typing code.'
                            }
                        ]
                        
                        for question_data in questions:
                            Question.objects.create(
                                quiz=quiz,
                                **question_data
                            )
                        
                        self.stdout.write(f'  🧩 Added quiz with {len(questions)} questions')
                
                created_courses.append(course)
            else:
                self.stdout.write(f'⚠️  Course already exists: {course.title}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎉 Successfully created {len(created_courses)} sample courses!\n'
                f'📊 Total courses in database: {Course.objects.count()}\n'
                f'📚 Total lessons: {Lesson.objects.count()}\n'
                f'🧩 Total quizzes: {Quiz.objects.count()}\n'
                f'❓ Total questions: {Question.objects.count()}'
            )
        )
