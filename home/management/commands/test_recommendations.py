from django.core.management.base import BaseCommand
from django.db.models import Q
from courses.models import Course
from home.course_recommendations import recommend_courses, INTEREST_TO_CATEGORY_MAP


class Command(BaseCommand):
    help = 'Test course recommendation system and diagnose issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--age',
            type=int,
            default=8,
            help='Student age (default: 8)'
        )
        parser.add_argument(
            '--interests',
            type=str,
            nargs='+',
            default=['Coding'],
            help='Interest areas (default: Coding)'
        )
        parser.add_argument(
            '--skills',
            type=str,
            choices=['beginner', 'intermediate', 'advanced'],
            default='beginner',
            help='Computer skills level (default: beginner)'
        )
        parser.add_argument(
            '--course-title',
            type=str,
            help='Search for a specific course by title (e.g., "Scratch")'
        )
        parser.add_argument(
            '--list-all',
            action='store_true',
            help='List all published courses in database'
        )

    def handle(self, *args, **options):
        student_age = options['age']
        interest_areas = options['interests']
        computer_skills_level = options['skills']
        course_title_filter = options.get('course_title')
        list_all = options['list_all']

        self.stdout.write(self.style.SUCCESS('\n=== Course Recommendation Test ===\n'))
        
        # List all published courses if requested
        if list_all:
            self.list_all_courses()
            return

        # Search for specific course if requested
        if course_title_filter:
            self.find_course(course_title_filter)
            return

        # Show test parameters
        self.stdout.write(f'Test Parameters:')
        self.stdout.write(f'  Student Age: {student_age}')
        self.stdout.write(f'  Interest Areas: {interest_areas}')
        self.stdout.write(f'  Computer Skills: {computer_skills_level}')
        self.stdout.write('')

        # Get all published courses
        all_courses = Course.objects.filter(status='published')
        self.stdout.write(f'Total published courses in database: {all_courses.count()}\n')

        # Check for Scratch or coding-related courses
        self.stdout.write('=== Searching for Coding/Programming Courses ===')
        coding_categories = INTEREST_TO_CATEGORY_MAP.get('Coding', [])
        self.stdout.write(f'Expected categories for "Coding": {coding_categories}\n')

        coding_courses = all_courses.filter(
            Q(category__in=coding_categories) |
            Q(title__icontains='coding') |
            Q(title__icontains='scratch') |
            Q(title__icontains='programming')
        )
        
        self.stdout.write(f'Found {coding_courses.count()} potential coding courses:')
        for course in coding_courses:
            self.stdout.write(f'  - {course.title}')
            self.stdout.write(f'    Category: {course.category}')
            self.stdout.write(f'    Age Range: {course.age_range}')
            self.stdout.write(f'    Level: {course.level}')
            self.stdout.write(f'    Required Skills: {course.required_computer_skills_level}')
            self.stdout.write(f'    Status: {course.status}')
            self.stdout.write('')

        # Test recommendation function
        self.stdout.write('\n=== Testing Recommendation Function ===\n')
        
        recommendations = recommend_courses(
            student_age=student_age,
            interest_areas=interest_areas,
            computer_skills_level=computer_skills_level,
            limit=10  # Get more results for testing
        )

        self.stdout.write(f'Found {len(recommendations)} recommendations:\n')

        if not recommendations:
            self.stdout.write(self.style.WARNING('⚠️  NO RECOMMENDATIONS FOUND'))
            self.stdout.write('\nDebugging why no courses matched...\n')
            self.debug_no_recommendations(all_courses, student_age, interest_areas, computer_skills_level)
        else:
            for idx, rec in enumerate(recommendations, 1):
                course = rec['course']
                self.stdout.write(self.style.SUCCESS(f'{idx}. {course.title}'))
                self.stdout.write(f'   Score: {rec["matchScore"]}')
                self.stdout.write(f'   Category: {course.category}')
                self.stdout.write(f'   Age Range: {course.age_range}')
                self.stdout.write(f'   Required Skills: {course.required_computer_skills_level}')
                self.stdout.write(f'   Reasons: {", ".join(rec["matchReasons"])}')
                self.stdout.write('')

        # Specifically check for Scratch course
        self.stdout.write('\n=== Checking for Scratch Course ===')
        scratch_courses = all_courses.filter(
            Q(title__icontains='scratch') |
            Q(title__icontains='Scratch')
        )
        
        if scratch_courses.exists():
            for course in scratch_courses:
                self.stdout.write(f'\nFound Scratch course: "{course.title}"')
                self.stdout.write(f'  Category: {course.category}')
                self.stdout.write(f'  Age Range: {course.age_range}')
                self.stdout.write(f'  Level: {course.level}')
                self.stdout.write(f'  Required Skills: {course.required_computer_skills_level}')
                self.stdout.write(f'  Status: {course.status}')
                
                # Check why it's not being recommended
                self.stdout.write('\n  Checking why it\'s not recommended:')
                self.check_course_match(course, student_age, interest_areas, computer_skills_level)
        else:
            self.stdout.write(self.style.WARNING('  ⚠️  No Scratch course found in database'))

    def list_all_courses(self):
        """List all published courses"""
        courses = Course.objects.filter(status='published').order_by('title')
        self.stdout.write(f'\nAll Published Courses ({courses.count()}):\n')
        
        for course in courses:
            self.stdout.write(f'  - {course.title}')
            self.stdout.write(f'    Category: {course.category}')
            self.stdout.write(f'    Age: {course.age_range}')
            self.stdout.write(f'    Skills: {course.required_computer_skills_level}')
            self.stdout.write(f'    Status: {course.status}')
            self.stdout.write('')

    def find_course(self, title_filter):
        """Find a specific course by title"""
        courses = Course.objects.filter(
            Q(title__icontains=title_filter) |
            Q(title__icontains=title_filter.lower())
        )
        
        if not courses.exists():
            self.stdout.write(self.style.ERROR(f'No courses found matching "{title_filter}"'))
            return
        
        self.stdout.write(f'Found {courses.count()} course(s) matching "{title_filter}":\n')
        
        for course in courses:
            self.stdout.write(f'Title: {course.title}')
            self.stdout.write(f'ID: {course.id}')
            self.stdout.write(f'Category: {course.category}')
            self.stdout.write(f'Age Range: {course.age_range}')
            self.stdout.write(f'Level: {course.level}')
            self.stdout.write(f'Required Skills: {course.required_computer_skills_level}')
            self.stdout.write(f'Status: {course.status}')
            self.stdout.write(f'Featured: {course.featured}')
            self.stdout.write(f'Popular: {course.popular}')
            self.stdout.write('')

    def check_course_match(self, course, student_age, interest_areas, computer_skills_level):
        """Check why a specific course matches or doesn't match"""
        from home.course_recommendations import (
            is_age_match, is_category_match, normalize_category
        )
        
        # Check age match
        age_match = is_age_match(student_age, course.age_range)
        self.stdout.write(f'  Age Match: {"✅ YES" if age_match else "❌ NO"}')
        if course.age_range:
            from home.course_recommendations import parse_age_range
            age_range = parse_age_range(course.age_range)
            if age_range:
                min_age, max_age = age_range
                self.stdout.write(f'    Student age {student_age} is {"WITHIN" if min_age <= student_age <= max_age else "OUTSIDE"} range {min_age}-{max_age}')
            else:
                self.stdout.write(f'    ⚠️  Could not parse age range: "{course.age_range}"')
        else:
            self.stdout.write(f'    ⚠️  Course has no age_range set')
        
        # Check category match
        category_match = is_category_match(interest_areas, course.category)
        self.stdout.write(f'  Category Match: {"✅ YES" if category_match else "❌ NO"}')
        if not category_match:
            self.stdout.write(f'    Course category: "{course.category}"')
            for interest in interest_areas:
                categories = INTEREST_TO_CATEGORY_MAP.get(interest, [])
                normalized_course_cat = normalize_category(course.category)
                matched = any(normalize_category(cat) == normalized_course_cat for cat in categories)
                self.stdout.write(f'    Interest "{interest}" maps to: {categories}')
                self.stdout.write(f'    Match found: {"✅ YES" if matched else "❌ NO"}')
        
        # Check skills match
        self.stdout.write(f'  Skills Match:')
        self.stdout.write(f'    Course requires: {course.required_computer_skills_level or "not set (uses level)"}')
        self.stdout.write(f'    Student has: {computer_skills_level}')
        
        if course.required_computer_skills_level and course.required_computer_skills_level != 'any':
            if course.required_computer_skills_level == computer_skills_level:
                self.stdout.write(f'    Result: ✅ Perfect match')
            elif (
                (course.required_computer_skills_level == 'beginner' and computer_skills_level in ['intermediate', 'advanced']) or
                (course.required_computer_skills_level == 'intermediate' and computer_skills_level == 'advanced')
            ):
                self.stdout.write(f'    Result: ✅ Student exceeds requirements')
            else:
                self.stdout.write(f'    Result: ❌ Student skills below minimum (EXCLUDED)')
        elif course.required_computer_skills_level == 'any':
            self.stdout.write(f'    Result: ✅ Course accepts any level')
        else:
            self.stdout.write(f'    Result: ⚠️  Using course.level ({course.level}) as fallback')

    def debug_no_recommendations(self, all_courses, student_age, interest_areas, computer_skills_level):
        """Debug why no recommendations were found"""
        from home.course_recommendations import (
            is_age_match, is_category_match, normalize_category
        )
        
        self.stdout.write('Checking all published courses:\n')
        
        for course in all_courses[:20]:  # Check first 20 courses
            self.stdout.write(f'\nCourse: {course.title}')
            
            # Age check
            age_match = is_age_match(student_age, course.age_range)
            self.stdout.write(f'  Age ({course.age_range}): {"✅" if age_match else "❌"}')
            
            # Category check
            category_match = is_category_match(interest_areas, course.category)
            self.stdout.write(f'  Category ({course.category}): {"✅" if category_match else "❌"}')
            
            # Skills check
            required_skills = course.required_computer_skills_level
            if required_skills and required_skills != 'any':
                if required_skills == computer_skills_level:
                    skills_ok = True
                elif (
                    (required_skills == 'beginner' and computer_skills_level in ['intermediate', 'advanced']) or
                    (required_skills == 'intermediate' and computer_skills_level == 'advanced')
                ):
                    skills_ok = True
                else:
                    skills_ok = False
            else:
                skills_ok = True
            
            self.stdout.write(f'  Skills ({required_skills or "any"}): {"✅" if skills_ok else "❌"}')
            
            if age_match and category_match and skills_ok:
                self.stdout.write(self.style.SUCCESS('  → Should be recommended!'))
            else:
                self.stdout.write(self.style.WARNING('  → Excluded'))

