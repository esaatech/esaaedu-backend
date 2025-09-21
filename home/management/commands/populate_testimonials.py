from django.core.management.base import BaseCommand
from courses.models import CourseReview, Course
from django.contrib.auth import get_user_model
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Populate sample testimonials for the landing page'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing testimonials before creating new ones',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write("Clearing existing testimonials...")
            CourseReview.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Cleared existing testimonials"))

        self.stdout.write("Creating sample testimonials...")

        # Get some courses to attach reviews to
        courses = Course.objects.filter(status='published')
        if not courses.exists():
            self.stdout.write(
                self.style.ERROR("No published courses found. Please create some courses first.")
            )
            return

        # Sample testimonials matching your frontend design
        testimonials_data = [
            {
                'parent_name': 'Sarah M.',
                'student_name': 'Alex',
                'student_age': 12,
                'rating': 5,
                'review_text': "Alex went from knowing nothing about coding to building his own game in just 6 weeks! The instructors are amazing and really know how to keep kids engaged.",
                'course_category': 'Game Development',
                'is_featured': True,
                'is_verified': True,
            },
            {
                'parent_name': 'Emily Chen',
                'student_name': 'Sophia',
                'student_age': 9,
                'rating': 5,
                'review_text': "Sophia absolutely loves her Scratch classes! She's created 3 different animated stories and can't wait to show them to everyone. Worth every penny!",
                'course_category': 'Scratch Programming',
                'is_featured': True,
                'is_verified': True,
            },
            {
                'parent_name': 'Michael R.',
                'student_name': 'Twins',
                'student_age': 14,
                'rating': 5,
                'review_text': "Both my kids are taking web development and they built a website for our family restaurant! The practical projects make learning so much more meaningful.",
                'course_category': 'Web Development',
                'is_featured': True,
                'is_verified': True,
            },
            {
                'parent_name': 'Jennifer L.',
                'student_name': 'Emma',
                'student_age': 10,
                'rating': 5,
                'review_text': "Emma was hesitant about coding at first, but the Python course made it so fun! She's now teaching her little brother what she learned.",
                'course_category': 'Python Programming',
                'is_featured': True,
                'is_verified': True,
            },
            {
                'parent_name': 'David K.',
                'student_name': 'Liam',
                'student_age': 11,
                'rating': 5,
                'review_text': "The robotics course exceeded our expectations. Liam built a working robot and learned so much about engineering concepts. Highly recommended!",
                'course_category': 'Robotics',
                'is_featured': True,
                'is_verified': True,
            },
            {
                'parent_name': 'Maria S.',
                'student_name': 'Isabella',
                'student_age': 8,
                'rating': 5,
                'review_text': "Isabella's confidence has grown so much through these coding classes. She's not afraid to try new things and loves solving problems!",
                'course_category': 'Computer Science',
                'is_featured': True,
                'is_verified': True,
            },
            {
                'parent_name': 'Robert T.',
                'student_name': 'Noah',
                'student_age': 13,
                'rating': 5,
                'review_text': "Noah learned JavaScript and created an interactive website for his school project. The teachers are patient and really understand how kids learn best.",
                'course_category': 'JavaScript',
                'is_featured': True,
                'is_verified': True,
            },
            {
                'parent_name': 'Lisa W.',
                'student_name': 'Ava',
                'student_age': 7,
                'rating': 5,
                'review_text': "Ava loves the visual programming course! She's created so many fun animations and games. The small class sizes make a huge difference.",
                'course_category': 'Visual Programming',
                'is_featured': True,
                'is_verified': True,
            },
        ]

        created_count = 0
        for testimonial_data in testimonials_data:
            # Find a course with matching category
            course = courses.filter(category__icontains=testimonial_data['course_category']).first()
            if not course:
                # If no exact match, pick a random course
                course = random.choice(courses)

            # Create the review
            review = CourseReview.objects.create(
                course=course,
                parent_name=testimonial_data['parent_name'],
                student_name=testimonial_data['student_name'],
                student_age=testimonial_data['student_age'],
                rating=testimonial_data['rating'],
                review_text=testimonial_data['review_text'],
                is_featured=testimonial_data['is_featured'],
                is_verified=testimonial_data['is_verified'],
            )
            
            created_count += 1
            self.stdout.write(
                self.style.SUCCESS(f'Created testimonial: {review.parent_name} - {review.student_name}')
            )

        # Create some additional non-featured reviews for variety
        additional_reviews = [
            {
                'parent_name': 'Amanda P.',
                'student_name': 'Ethan',
                'student_age': 15,
                'rating': 4,
                'review_text': "Great course structure and helpful instructors. Ethan learned a lot about data science concepts.",
                'is_featured': False,
                'is_verified': True,
            },
            {
                'parent_name': 'Chris M.',
                'student_name': 'Maya',
                'student_age': 9,
                'rating': 5,
                'review_text': "Maya's creativity has really flourished with these coding classes. She's always excited to show us her new projects!",
                'is_featured': False,
                'is_verified': True,
            },
            {
                'parent_name': 'Rachel G.',
                'student_name': 'Oliver',
                'student_age': 12,
                'rating': 4,
                'review_text': "The mobile app development course was challenging but very rewarding. Oliver built his first app!",
                'is_featured': False,
                'is_verified': True,
            },
        ]

        for review_data in additional_reviews:
            course = random.choice(courses)
            CourseReview.objects.create(
                course=course,
                parent_name=review_data['parent_name'],
                student_name=review_data['student_name'],
                student_age=review_data['student_age'],
                rating=review_data['rating'],
                review_text=review_data['review_text'],
                is_featured=review_data['is_featured'],
                is_verified=review_data['is_verified'],
            )
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f'\nSuccessfully created {created_count} testimonials!')
        )
        self.stdout.write(
            self.style.SUCCESS(f'Featured testimonials: {CourseReview.objects.filter(is_featured=True).count()}')
        )
        self.stdout.write(
            self.style.SUCCESS(f'Total reviews: {CourseReview.objects.count()}')
        )
