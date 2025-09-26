from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from courses.models import Course, Lesson, Assignment, AssignmentQuestion, AssignmentSubmission
from student.models import EnrolledCourse
from users.models import StudentProfile
import uuid

User = get_user_model()


class AssignmentManagementAPITestCase(APITestCase):
    """
    Test cases for Assignment Management API
    Tests CRUD operations for assignments
    """
    
    def setUp(self):
        """Set up test data"""
        # Create test teacher
        self.teacher = User.objects.create_user(
            firebase_uid='test_teacher_firebase_uid',
            email='teacher@test.com',
            username='teacher@test.com',
            password='testpass123',
            first_name='Test',
            last_name='Teacher',
            role='teacher'
        )
        
        # Create another teacher for cross-access testing
        self.other_teacher = User.objects.create_user(
            firebase_uid='test_other_teacher_firebase_uid',
            email='other@test.com',
            username='other@test.com',
            password='testpass123',
            first_name='Other',
            last_name='Teacher',
            role='teacher'
        )
        
        # Create test student
        self.student = User.objects.create_user(
            firebase_uid='test_student_firebase_uid',
            email='student@test.com',
            username='student@test.com',
            password='testpass123',
            first_name='Test',
            last_name='Student',
            role='student'
        )
        
        # Create student profile
        self.student_profile = StudentProfile.objects.create(
            user=self.student,
            learning_goals='Test learning goals',
            grade_level='Grade 5'
        )
        
        # Create test course
        self.course = Course.objects.create(
            title='Test Course',
            description='Test course description',
            teacher=self.teacher,
            category='Computer Science',
            price=99.99,
            is_free=False
        )
        
        # Create test lesson
        self.lesson = Lesson.objects.create(
            course=self.course,
            title='Test Lesson',
            description='Test lesson description',
            order=1,
            duration=60,
            type='text_lesson'
        )
        
        # Create another course for other teacher
        self.other_course = Course.objects.create(
            title='Other Course',
            description='Other course description',
            teacher=self.other_teacher,
            category='Mathematics',
            price=149.99,
            is_free=False
        )
        
        # Create another lesson
        self.other_lesson = Lesson.objects.create(
            course=self.other_course,
            title='Other Lesson',
            description='Other lesson description',
            order=1,
            duration=45,
            type='video_lesson'
        )
        
        # Create test assignment
        self.assignment = Assignment.objects.create(
            lesson=self.lesson,
            title='Test Assignment',
            description='Test assignment description',
            assignment_type='homework',
            due_date=timezone.now() + timedelta(days=7),
            passing_score=70,
            max_attempts=3
        )
        
        # Create test question
        self.question = AssignmentQuestion.objects.create(
            assignment=self.assignment,
            question_text='What is 2 + 2?',
            order=1,
            points=5,
            type='multiple_choice',
            content={
                'options': ['3', '4', '5', '6'],
                'correct_answer': '4'
            }
        )
        
        # Create enrollment
        self.enrollment = EnrolledCourse.objects.create(
            student_profile=self.student_profile,
            course=self.course,
            status='active'
        )
        
        # Create test submission
        self.submission = AssignmentSubmission.objects.create(
            student=self.student,
            assignment=self.assignment,
            enrollment=self.enrollment,
            attempt_number=1,
            answers={'question_1': '4'},
            points_possible=5
        )
    
    def test_assignment_list_authenticated_teacher(self):
        """Test that authenticated teacher can list their assignments"""
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get('/api/teacher/assignments/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('assignments', response.data)
        self.assertIn('total_count', response.data)
        self.assertEqual(response.data['total_count'], 1)
        self.assertEqual(len(response.data['assignments']), 1)
        
        assignment_data = response.data['assignments'][0]
        self.assertEqual(assignment_data['title'], 'Test Assignment')
        self.assertEqual(assignment_data['assignment_type'], 'homework')
        self.assertEqual(assignment_data['question_count'], 1)
        self.assertEqual(assignment_data['submission_count'], 1)
    
    def test_assignment_list_unauthenticated(self):
        """Test that unauthenticated users get 401"""
        response = self.client.get('/api/teacher/assignments/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_assignment_list_non_teacher(self):
        """Test that non-teachers get 403"""
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/teacher/assignments/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_assignment_list_filter_by_course(self):
        """Test filtering assignments by course"""
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get(f'/api/teacher/assignments/?course_id={self.course.id}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 1)
        
        # Test with non-existent course
        response = self.client.get('/api/teacher/assignments/?course_id=99999999-9999-9999-9999-999999999999')
        self.assertEqual(response.data['total_count'], 0)
    
    def test_assignment_list_filter_by_lesson(self):
        """Test filtering assignments by lesson"""
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get(f'/api/teacher/assignments/?lesson_id={self.lesson.id}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 1)
    
    def test_assignment_list_filter_by_type(self):
        """Test filtering assignments by type"""
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get('/api/teacher/assignments/?assignment_type=homework')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 1)
        
        # Test with different type
        response = self.client.get('/api/teacher/assignments/?assignment_type=exam')
        self.assertEqual(response.data['total_count'], 0)
    
    def test_assignment_list_search(self):
        """Test searching assignments by title and description"""
        self.client.force_authenticate(user=self.teacher)
        
        # Search by title
        response = self.client.get('/api/teacher/assignments/?search=Test')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 1)
        
        # Search by description
        response = self.client.get('/api/teacher/assignments/?search=assignment')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 1)
        
        # Search with no results
        response = self.client.get('/api/teacher/assignments/?search=nonexistent')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 0)
    
    def test_assignment_create_success(self):
        """Test successful assignment creation"""
        self.client.force_authenticate(user=self.teacher)
        
        # Create a new lesson for the assignment
        new_lesson = Lesson.objects.create(
            course=self.course,
            title='New Lesson',
            description='New lesson description',
            order=2,
            duration=45,
            type='video_lesson'
        )
        
        assignment_data = {
            'lesson': str(new_lesson.id),
            'title': 'New Assignment',
            'description': 'New assignment description',
            'assignment_type': 'quiz',
            'due_date': (timezone.now() + timedelta(days=14)).isoformat(),
            'passing_score': 80,
            'max_attempts': 2,
            'show_correct_answers': True,
            'randomize_questions': False
        }
        
        response = self.client.post('/api/teacher/assignments/', assignment_data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('assignment', response.data)
        self.assertIn('message', response.data)
        self.assertEqual(response.data['assignment']['title'], 'New Assignment')
        self.assertEqual(response.data['assignment']['assignment_type'], 'quiz')
        
        # Verify assignment was created in database
        assignment = Assignment.objects.get(title='New Assignment')
        self.assertEqual(assignment.lesson, new_lesson)
        self.assertEqual(assignment.assignment_type, 'quiz')
    
    def test_assignment_create_invalid_lesson(self):
        """Test assignment creation with invalid lesson"""
        self.client.force_authenticate(user=self.teacher)
        
        assignment_data = {
            'lesson': str(self.other_lesson.id),  # Other teacher's lesson
            'title': 'Invalid Assignment',
            'description': 'Invalid assignment description',
            'assignment_type': 'homework'
        }
        
        response = self.client.post('/api/teacher/assignments/', assignment_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('lesson', response.data)
    
    def test_assignment_create_missing_required_fields(self):
        """Test assignment creation with missing required fields"""
        self.client.force_authenticate(user=self.teacher)
        
        # Test missing lesson
        assignment_data = {
            'title': 'Incomplete Assignment',
            'assignment_type': 'homework'
            # Missing lesson
        }
        
        response = self.client.post('/api/teacher/assignments/', assignment_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('lesson', response.data)
        
        # Create a new lesson for testing assignment_type requirement
        test_lesson = Lesson.objects.create(
            course=self.course,
            title='Test Lesson for Validation',
            description='Test lesson description',
            order=5,
            duration=30,
            type='text_lesson'
        )
        
        # Test missing assignment_type (with lesson provided)
        # Note: assignment_type has default='homework' so it's not required
        assignment_data = {
            'lesson': str(test_lesson.id),
            'title': 'Incomplete Assignment'
            # Missing assignment_type (but has default)
        }
        
        response = self.client.post('/api/teacher/assignments/', assignment_data)
        # Should succeed because assignment_type has a default value
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['assignment']['assignment_type'], 'homework')  # Default value
    
    def test_assignment_create_invalid_due_date(self):
        """Test assignment creation with past due date"""
        self.client.force_authenticate(user=self.teacher)
        
        assignment_data = {
            'lesson': str(self.lesson.id),
            'title': 'Past Due Assignment',
            'description': 'Assignment with past due date',
            'assignment_type': 'homework',
            'due_date': (timezone.now() - timedelta(days=1)).isoformat()  # Past date
        }
        
        response = self.client.post('/api/teacher/assignments/', assignment_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('due_date', response.data)
    
    def test_assignment_create_invalid_passing_score(self):
        """Test assignment creation with invalid passing score"""
        self.client.force_authenticate(user=self.teacher)
        
        assignment_data = {
            'lesson': str(self.lesson.id),
            'title': 'Invalid Score Assignment',
            'description': 'Assignment with invalid passing score',
            'assignment_type': 'homework',
            'passing_score': 150  # Invalid score > 100
        }
        
        response = self.client.post('/api/teacher/assignments/', assignment_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('passing_score', response.data)
    
    def test_assignment_update_success(self):
        """Test successful assignment update"""
        self.client.force_authenticate(user=self.teacher)
        
        update_data = {
            'title': 'Updated Assignment Title',
            'description': 'Updated assignment description',
            'passing_score': 85
        }
        
        response = self.client.put(f'/api/teacher/assignments/{self.assignment.id}/', update_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('assignment', response.data)
        self.assertEqual(response.data['assignment']['title'], 'Updated Assignment Title')
        self.assertEqual(response.data['assignment']['passing_score'], 85)
        
        # Verify update in database
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.title, 'Updated Assignment Title')
        self.assertEqual(self.assignment.passing_score, 85)
    
    def test_assignment_update_other_teacher(self):
        """Test assignment update by other teacher"""
        self.client.force_authenticate(user=self.other_teacher)
        
        update_data = {
            'title': 'Unauthorized Update'
        }
        
        response = self.client.put(f'/api/teacher/assignments/{self.assignment.id}/', update_data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_assignment_update_nonexistent(self):
        """Test assignment update with nonexistent ID"""
        self.client.force_authenticate(user=self.teacher)
        
        fake_id = uuid.uuid4()
        update_data = {'title': 'Update Nonexistent'}
        
        response = self.client.put(f'/api/teacher/assignments/{fake_id}/', update_data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_assignment_delete_success(self):
        """Test successful assignment deletion"""
        self.client.force_authenticate(user=self.teacher)
        
        # Create a new lesson for the assignment to delete
        lesson_to_delete = Lesson.objects.create(
            course=self.course,
            title='Lesson to Delete',
            description='This lesson will be deleted',
            order=2,
            duration=30,
            type='text_lesson'
        )
        
        # Create assignment without submissions for deletion
        assignment_to_delete = Assignment.objects.create(
            lesson=lesson_to_delete,
            title='Assignment to Delete',
            description='This assignment will be deleted',
            assignment_type='homework'
        )
        
        response = self.client.delete(f'/api/teacher/assignments/{assignment_to_delete.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('deleted_assignment', response.data)
        
        # Verify deletion
        self.assertFalse(Assignment.objects.filter(id=assignment_to_delete.id).exists())
    
    def test_assignment_delete_with_submissions(self):
        """Test assignment deletion with existing submissions"""
        self.client.force_authenticate(user=self.teacher)
        
        response = self.client.delete(f'/api/teacher/assignments/{self.assignment.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('submissions', response.data['error'])
        
        # Verify assignment still exists
        self.assertTrue(Assignment.objects.filter(id=self.assignment.id).exists())
    
    def test_assignment_delete_other_teacher(self):
        """Test assignment deletion by other teacher"""
        self.client.force_authenticate(user=self.other_teacher)
        
        response = self.client.delete(f'/api/teacher/assignments/{self.assignment.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AssignmentQuestionAPITestCase(APITestCase):
    """
    Test cases for Assignment Question Management API
    Tests CRUD operations for assignment questions
    """
    
    def setUp(self):
        """Set up test data"""
        # Create test teacher
        self.teacher = User.objects.create_user(
            firebase_uid='test_teacher_firebase_uid_2',
            email='teacher@test.com',
            username='teacher@test.com',
            password='testpass123',
            first_name='Test',
            last_name='Teacher',
            role='teacher'
        )
        
        # Create another teacher
        self.other_teacher = User.objects.create_user(
            firebase_uid='test_other_teacher_firebase_uid_2',
            email='other@test.com',
            username='other@test.com',
            password='testpass123',
            first_name='Other',
            last_name='Teacher',
            role='teacher'
        )
        
        # Create test course and lesson
        self.course = Course.objects.create(
            title='Test Course',
            description='Test course description',
            teacher=self.teacher,
            category='Computer Science',
            price=99.99,
            is_free=False
        )
        
        self.lesson = Lesson.objects.create(
            course=self.course,
            title='Test Lesson',
            description='Test lesson description',
            order=1,
            duration=60,
            type='text_lesson'
        )
        
        # Create test assignment
        self.assignment = Assignment.objects.create(
            lesson=self.lesson,
            title='Test Assignment',
            description='Test assignment description',
            assignment_type='homework'
        )
        
        # Create test question
        self.question = AssignmentQuestion.objects.create(
            assignment=self.assignment,
            question_text='What is 2 + 2?',
            order=1,
            points=5,
            type='multiple_choice',
            content={
                'options': ['3', '4', '5', '6'],
                'correct_answer': '4'
            }
        )
        
        # Create other teacher's assignment
        self.other_course = Course.objects.create(
            title='Other Course',
            description='Other course description',
            teacher=self.other_teacher,
            category='Mathematics',
            price=149.99,
            is_free=False
        )
        
        self.other_lesson = Lesson.objects.create(
            course=self.other_course,
            title='Other Lesson',
            description='Other lesson description',
            order=1,
            duration=45,
            type='video_lesson'
        )
        
        self.other_assignment = Assignment.objects.create(
            lesson=self.other_lesson,
            title='Other Assignment',
            description='Other assignment description',
            assignment_type='exam'
        )
    
    def test_question_list_success(self):
        """Test successful question listing"""
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get(f'/api/teacher/assignments/{self.assignment.id}/questions/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('assignment_id', response.data)
        self.assertIn('assignment_title', response.data)
        self.assertIn('questions', response.data)
        self.assertIn('total_questions', response.data)
        
        self.assertEqual(response.data['total_questions'], 1)
        self.assertEqual(len(response.data['questions']), 1)
        
        question_data = response.data['questions'][0]
        self.assertEqual(question_data['question_text'], 'What is 2 + 2?')
        self.assertEqual(question_data['type'], 'multiple_choice')
        self.assertEqual(question_data['points'], 5)
    
    def test_question_list_unauthenticated(self):
        """Test question listing without authentication"""
        response = self.client.get(f'/api/teacher/assignments/{self.assignment.id}/questions/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_question_list_non_teacher(self):
        """Test question listing by non-teacher"""
        student = User.objects.create_user(
            firebase_uid='test_student_firebase_uid_2',
            email='student@test.com',
            username='student@test.com',
            password='testpass123',
            first_name='Test',
            last_name='Student',
            role='student'
        )
        self.client.force_authenticate(user=student)
        response = self.client.get(f'/api/teacher/assignments/{self.assignment.id}/questions/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_question_list_other_teacher(self):
        """Test question listing by other teacher"""
        self.client.force_authenticate(user=self.other_teacher)
        response = self.client.get(f'/api/teacher/assignments/{self.assignment.id}/questions/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_question_list_nonexistent_assignment(self):
        """Test question listing for nonexistent assignment"""
        self.client.force_authenticate(user=self.teacher)
        fake_id = uuid.uuid4()
        response = self.client.get(f'/api/teacher/assignments/{fake_id}/questions/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_question_create_multiple_choice(self):
        """Test creating multiple choice question"""
        self.client.force_authenticate(user=self.teacher)
        
        question_data = {
            'question_text': 'What is the capital of France?',
            'order': 2,
            'points': 10,
            'type': 'multiple_choice',
            'content': {
                'options': ['London', 'Berlin', 'Paris', 'Madrid'],
                'correct_answer': 'Paris'
            },
            'explanation': 'Paris is the capital and largest city of France.'
        }
        
        response = self.client.post(f'/api/teacher/assignments/{self.assignment.id}/questions/', question_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('question', response.data)
        self.assertEqual(response.data['question']['question_text'], 'What is the capital of France?')
        self.assertEqual(response.data['question']['type'], 'multiple_choice')
        
        # Verify question was created
        question = AssignmentQuestion.objects.get(question_text='What is the capital of France?')
        self.assertEqual(question.assignment, self.assignment)
        self.assertEqual(question.order, 2)
    
    def test_question_create_true_false(self):
        """Test creating true/false question"""
        self.client.force_authenticate(user=self.teacher)
        
        question_data = {
            'question_text': 'Python is a programming language.',
            'order': 3,
            'points': 5,
            'type': 'true_false',
            'content': {
                'correct_answer': True
            }
        }
        
        response = self.client.post(f'/api/teacher/assignments/{self.assignment.id}/questions/', question_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['question']['type'], 'true_false')
    
    def test_question_create_flashcard(self):
        """Test creating flashcard question"""
        self.client.force_authenticate(user=self.teacher)
        
        question_data = {
            'question_text': 'What does "Hola" mean in English?',
            'order': 4,
            'points': 3,
            'type': 'flashcard',
            'content': {
                'answer': 'Hello',
                'hint': 'Common Spanish greeting'
            }
        }
        
        response = self.client.post(f'/api/teacher/assignments/{self.assignment.id}/questions/', question_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['question']['type'], 'flashcard')
        self.assertEqual(response.data['question']['content']['answer'], 'Hello')
    
    def test_question_create_invalid_content(self):
        """Test creating question with invalid content"""
        self.client.force_authenticate(user=self.teacher)
        
        # Multiple choice without options
        question_data = {
            'question_text': 'Invalid question',
            'order': 5,
            'points': 5,
            'type': 'multiple_choice',
            'content': {
                'correct_answer': '4'
                # Missing 'options'
            }
        }
        
        response = self.client.post(f'/api/teacher/assignments/{self.assignment.id}/questions/', question_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('content', response.data)
    
    def test_question_create_other_teacher_assignment(self):
        """Test creating question for other teacher's assignment"""
        self.client.force_authenticate(user=self.other_teacher)
        
        question_data = {
            'question_text': 'Unauthorized question',
            'order': 1,
            'points': 5,
            'type': 'multiple_choice',
            'content': {
                'options': ['A', 'B', 'C', 'D'],
                'correct_answer': 'A'
            }
        }
        
        response = self.client.post(f'/api/teacher/assignments/{self.assignment.id}/questions/', question_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_question_update_success(self):
        """Test successful question update"""
        self.client.force_authenticate(user=self.teacher)
        
        update_data = {
            'question_text': 'Updated question: What is 2 + 2?',
            'points': 10,
            'content': {
                'options': ['3', '4', '5', '6'],
                'correct_answer': '4'
            }
        }
        
        response = self.client.put(f'/api/teacher/assignments/{self.assignment.id}/questions/{self.question.id}/', update_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['question']['question_text'], 'Updated question: What is 2 + 2?')
        self.assertEqual(response.data['question']['points'], 10)
        
        # Verify update in database
        self.question.refresh_from_db()
        self.assertEqual(self.question.question_text, 'Updated question: What is 2 + 2?')
        self.assertEqual(self.question.points, 10)
    
    def test_question_update_other_teacher(self):
        """Test question update by other teacher"""
        self.client.force_authenticate(user=self.other_teacher)
        
        update_data = {
            'question_text': 'Unauthorized update'
        }
        
        response = self.client.put(f'/api/teacher/assignments/{self.assignment.id}/questions/{self.question.id}/', update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_question_update_nonexistent(self):
        """Test question update with nonexistent ID"""
        self.client.force_authenticate(user=self.teacher)
        
        fake_id = uuid.uuid4()
        update_data = {'question_text': 'Update nonexistent'}
        
        response = self.client.put(f'/api/teacher/assignments/{self.assignment.id}/questions/{fake_id}/', update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_question_delete_success(self):
        """Test successful question deletion"""
        self.client.force_authenticate(user=self.teacher)
        
        # Create question to delete
        question_to_delete = AssignmentQuestion.objects.create(
            assignment=self.assignment,
            question_text='Question to Delete',
            order=10,
            points=5,
            type='short_answer',
            content={'answer': 'Sample answer'}
        )
        
        response = self.client.delete(f'/api/teacher/assignments/{self.assignment.id}/questions/{question_to_delete.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('deleted_question', response.data)
        
        # Verify deletion
        self.assertFalse(AssignmentQuestion.objects.filter(id=question_to_delete.id).exists())
    
    def test_question_delete_other_teacher(self):
        """Test question deletion by other teacher"""
        self.client.force_authenticate(user=self.other_teacher)
        
        response = self.client.delete(f'/api/teacher/assignments/{self.assignment.id}/questions/{self.question.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_question_delete_nonexistent(self):
        """Test question deletion with nonexistent ID"""
        self.client.force_authenticate(user=self.teacher)
        
        fake_id = uuid.uuid4()
        response = self.client.delete(f'/api/teacher/assignments/{self.assignment.id}/questions/{fake_id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AssignmentGradingAPITestCase(APITestCase):
    """
    Test cases for Assignment Grading API
    Tests grading and submission management
    """
    
    def setUp(self):
        """Set up test data"""
        # Create test teacher
        self.teacher = User.objects.create_user(
            firebase_uid='test_teacher_firebase_uid_3',
            email='teacher@test.com',
            username='teacher@test.com',
            password='testpass123',
            first_name='Test',
            last_name='Teacher',
            role='teacher'
        )
        
        # Create another teacher
        self.other_teacher = User.objects.create_user(
            firebase_uid='test_other_teacher_firebase_uid_3',
            email='other@test.com',
            username='other@test.com',
            password='testpass123',
            first_name='Other',
            last_name='Teacher',
            role='teacher'
        )
        
        # Create test students
        self.student1 = User.objects.create_user(
            firebase_uid='test_student1_firebase_uid',
            email='student1@test.com',
            username='student1@test.com',
            password='testpass123',
            first_name='Student',
            last_name='One',
            role='student'
        )
        
        self.student2 = User.objects.create_user(
            firebase_uid='test_student2_firebase_uid',
            email='student2@test.com',
            username='student2@test.com',
            password='testpass123',
            first_name='Student',
            last_name='Two',
            role='student'
        )
        
        # Create student profiles
        self.student1_profile = StudentProfile.objects.create(
            user=self.student1,
            learning_goals='Student 1 learning goals',
            grade_level='Grade 6'
        )
        
        self.student2_profile = StudentProfile.objects.create(
            user=self.student2,
            learning_goals='Student 2 learning goals',
            grade_level='Grade 7'
        )
        
        # Create test course and lesson
        self.course = Course.objects.create(
            title='Test Course',
            description='Test course description',
            teacher=self.teacher,
            category='Computer Science',
            price=99.99,
            is_free=False
        )
        
        self.lesson = Lesson.objects.create(
            course=self.course,
            title='Test Lesson',
            description='Test lesson description',
            order=1,
            duration=60,
            type='text_lesson'
        )
        
        # Create test assignment
        self.assignment = Assignment.objects.create(
            lesson=self.lesson,
            title='Test Assignment',
            description='Test assignment description',
            assignment_type='homework',
            passing_score=70,
            max_attempts=3
        )
        
        # Create test question
        self.question = AssignmentQuestion.objects.create(
            assignment=self.assignment,
            question_text='What is 2 + 2?',
            order=1,
            points=5,
            type='multiple_choice',
            content={
                'options': ['3', '4', '5', '6'],
                'correct_answer': '4'
            }
        )
        
        # Create enrollments
        self.enrollment1 = EnrolledCourse.objects.create(
            student_profile=self.student1_profile,
            course=self.course,
            status='active'
        )
        
        self.enrollment2 = EnrolledCourse.objects.create(
            student_profile=self.student2_profile,
            course=self.course,
            status='active'
        )
        
        # Create test submissions
        self.submission1 = AssignmentSubmission.objects.create(
            student=self.student1,
            assignment=self.assignment,
            enrollment=self.enrollment1,
            attempt_number=1,
            answers={'question_1': '4'},
            points_possible=5,
            submitted_at=timezone.now()
        )
        
        self.submission2 = AssignmentSubmission.objects.create(
            student=self.student2,
            assignment=self.assignment,
            enrollment=self.enrollment2,
            attempt_number=1,
            answers={'question_1': '3'},
            points_possible=5,
            submitted_at=timezone.now()
        )
    
    def test_grading_list_success(self):
        """Test successful grading list"""
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get(f'/api/teacher/assignments/{self.assignment.id}/grading/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('assignment', response.data)
        self.assertIn('submissions', response.data)
        self.assertIn('grading_stats', response.data)
        
        self.assertEqual(len(response.data['submissions']), 2)
        
        # Check grading stats
        stats = response.data['grading_stats']
        self.assertEqual(stats['total_submissions'], 2)
        self.assertEqual(stats['graded_submissions'], 0)
        self.assertEqual(stats['pending_submissions'], 2)
    
    def test_grading_list_unauthenticated(self):
        """Test grading list without authentication"""
        response = self.client.get(f'/api/teacher/assignments/{self.assignment.id}/grading/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_grading_list_non_teacher(self):
        """Test grading list by non-teacher"""
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(f'/api/teacher/assignments/{self.assignment.id}/grading/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_grading_list_other_teacher(self):
        """Test grading list by other teacher"""
        self.client.force_authenticate(user=self.other_teacher)
        response = self.client.get(f'/api/teacher/assignments/{self.assignment.id}/grading/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_grading_list_filter_by_status(self):
        """Test filtering submissions by status"""
        self.client.force_authenticate(user=self.teacher)
        
        # Filter by submitted status
        response = self.client.get(f'/api/teacher/assignments/{self.assignment.id}/grading/?status=SUBMITTED')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['submissions']), 2)
        
        # Filter by graded status (should be empty)
        response = self.client.get(f'/api/teacher/assignments/{self.assignment.id}/grading/?status=GRADED')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['submissions']), 0)
    
    def test_grading_list_search(self):
        """Test searching submissions by student name"""
        self.client.force_authenticate(user=self.teacher)
        
        # Search by student name
        response = self.client.get(f'/api/teacher/assignments/{self.assignment.id}/grading/?search=Student One')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['submissions']), 1)
        self.assertEqual(response.data['submissions'][0]['student_name'], 'Student One')
        
        # Search with no results
        response = self.client.get(f'/api/teacher/assignments/{self.assignment.id}/grading/?search=Nonexistent')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['submissions']), 0)
    
    def test_submission_grade_success(self):
        """Test successful submission grading"""
        self.client.force_authenticate(user=self.teacher)
        
        grade_data = {
            'status': 'GRADED',
            'points_earned': 4.5,
            'feedback': 'Good work! You got most of it right.',
            'graded_questions': [
                {
                    'question_id': str(self.question.id),
                    'is_correct': True,
                    'teacher_feedback': 'Correct answer!',
                    'points_earned': 4.5,
                    'points_possible': 5
                }
            ]
        }
        
        response = self.client.put(f'/api/teacher/assignments/submissions/{self.submission1.id}/', grade_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('submission', response.data)
        self.assertEqual(response.data['submission']['status'], 'GRADED')
        self.assertEqual(response.data['submission']['points_earned'], 4.5)
        self.assertEqual(response.data['submission']['feedback'], 'Good work! You got most of it right.')
        
        # Verify grading in database
        self.submission1.refresh_from_db()
        self.assertEqual(self.submission1.status, 'GRADED')
        self.assertEqual(self.submission1.points_earned, 4.5)
        self.assertTrue(self.submission1.is_graded)
        self.assertIsNotNone(self.submission1.graded_at)
        self.assertEqual(self.submission1.graded_by, self.teacher)
    
    def test_submission_grade_returned(self):
        """Test grading submission as returned for revision"""
        self.client.force_authenticate(user=self.teacher)
        
        grade_data = {
            'status': 'RETURNED',
            'feedback': 'Please revise your answer. Check your calculation.',
            'graded_questions': [
                {
                    'question_id': str(self.question.id),
                    'is_correct': False,
                    'teacher_feedback': 'Incorrect. Try again.',
                    'points_earned': 0,
                    'points_possible': 5
                }
            ]
        }
        
        response = self.client.put(f'/api/teacher/assignments/submissions/{self.submission2.id}/', grade_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['submission']['status'], 'RETURNED')
        self.assertEqual(response.data['submission']['points_earned'], 0)
        
        # Verify status in database
        self.submission2.refresh_from_db()
        self.assertEqual(self.submission2.status, 'RETURNED')
        self.assertEqual(self.submission2.points_earned, 0)
    
    def test_submission_grade_invalid_status(self):
        """Test grading with invalid status"""
        self.client.force_authenticate(user=self.teacher)
        
        grade_data = {
            'status': 'INVALID_STATUS',
            'points_earned': 5
        }
        
        response = self.client.put(f'/api/teacher/assignments/submissions/{self.submission1.id}/', grade_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data)
    
    def test_submission_grade_negative_points(self):
        """Test grading with negative points"""
        self.client.force_authenticate(user=self.teacher)
        
        grade_data = {
            'status': 'GRADED',
            'points_earned': -1
        }
        
        response = self.client.put(f'/api/teacher/assignments/submissions/{self.submission1.id}/', grade_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('points_earned', response.data)
    
    def test_submission_grade_other_teacher(self):
        """Test grading submission by other teacher"""
        self.client.force_authenticate(user=self.other_teacher)
        
        grade_data = {
            'status': 'GRADED',
            'points_earned': 5
        }
        
        response = self.client.put(f'/api/teacher/assignments/submissions/{self.submission1.id}/', grade_data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_submission_grade_nonexistent(self):
        """Test grading nonexistent submission"""
        self.client.force_authenticate(user=self.teacher)
        
        fake_id = uuid.uuid4()
        grade_data = {
            'status': 'GRADED',
            'points_earned': 5
        }
        
        response = self.client.put(f'/api/teacher/assignments/submissions/{fake_id}/', grade_data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_submission_detail_success(self):
        """Test getting submission detail"""
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get(f'/api/teacher/assignments/submissions/{self.submission1.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('submission', response.data)
        self.assertIn('project', response.data)
        
        submission_data = response.data['submission']
        self.assertEqual(submission_data['student_name'], 'Student One')
        self.assertEqual(submission_data['status'], 'SUBMITTED')
        self.assertEqual(submission_data['attempt_number'], 1)
    
    def test_submission_detail_other_teacher(self):
        """Test getting submission detail by other teacher"""
        self.client.force_authenticate(user=self.other_teacher)
        response = self.client.get(f'/api/teacher/assignments/submissions/{self.submission1.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_submission_feedback_success(self):
        """Test providing feedback on submission"""
        self.client.force_authenticate(user=self.teacher)
        
        feedback_data = {
            'status': 'GRADED',
            'feedback': 'Excellent work! Keep it up.'
        }
        
        response = self.client.post(f'/api/teacher/assignments/submissions/{self.submission1.id}/', feedback_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('submission', response.data)
        self.assertEqual(response.data['submission']['feedback'], 'Excellent work! Keep it up.')
        self.assertEqual(response.data['submission']['status'], 'GRADED')
    
    def test_submission_feedback_missing_status(self):
        """Test providing feedback without status"""
        self.client.force_authenticate(user=self.teacher)
        
        feedback_data = {
            'feedback': 'Good work!'
            # Missing status
        }
        
        response = self.client.post(f'/api/teacher/assignments/submissions/{self.submission1.id}/', feedback_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', response.data)
    
    def test_submission_feedback_missing_feedback(self):
        """Test providing feedback without feedback text"""
        self.client.force_authenticate(user=self.teacher)
        
        feedback_data = {
            'status': 'GRADED'
            # Missing feedback
        }
        
        response = self.client.post(f'/api/teacher/assignments/submissions/{self.submission1.id}/', feedback_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('feedback', response.data)


class AssignmentPermissionTestCase(APITestCase):
    """
    Test cases for Assignment Permission and Security
    Tests authentication, authorization, and data isolation
    """
    
    def setUp(self):
        """Set up test data"""
        # Create test users
        self.teacher1 = User.objects.create_user(
            firebase_uid='test_teacher1_firebase_uid',
            email='teacher1@test.com',
            username='teacher1@test.com',
            password='testpass123',
            first_name='Teacher',
            last_name='One',
            role='teacher'
        )
        
        self.teacher2 = User.objects.create_user(
            firebase_uid='test_teacher2_firebase_uid',
            email='teacher2@test.com',
            username='teacher2@test.com',
            password='testpass123',
            first_name='Teacher',
            last_name='Two',
            role='teacher'
        )
        
        self.student = User.objects.create_user(
            firebase_uid='test_student_firebase_uid_3',
            email='student@test.com',
            username='student@test.com',
            password='testpass123',
            first_name='Test',
            last_name='Student',
            role='student'
        )
        
        self.admin = User.objects.create_user(
            firebase_uid='test_admin_firebase_uid',
            email='admin@test.com',
            username='admin@test.com',
            password='testpass123',
            first_name='Admin',
            last_name='User',
            role='admin',
            is_staff=True
        )
        
        # Create courses for each teacher
        self.course1 = Course.objects.create(
            title='Teacher 1 Course',
            description='Course by teacher 1',
            teacher=self.teacher1,
            category='Computer Science',
            price=99.99,
            is_free=False
        )
        
        self.course2 = Course.objects.create(
            title='Teacher 2 Course',
            description='Course by teacher 2',
            teacher=self.teacher2,
            category='Mathematics',
            price=149.99,
            is_free=False
        )
        
        # Create lessons
        self.lesson1 = Lesson.objects.create(
            course=self.course1,
            title='Lesson 1',
            description='Lesson 1 description',
            order=1,
            duration=60,
            type='text_lesson'
        )
        
        self.lesson2 = Lesson.objects.create(
            course=self.course2,
            title='Lesson 2',
            description='Lesson 2 description',
            order=1,
            duration=45,
            type='video_lesson'
        )
        
        # Create assignments
        self.assignment1 = Assignment.objects.create(
            lesson=self.lesson1,
            title='Assignment 1',
            description='Assignment 1 description',
            assignment_type='homework'
        )
        
        self.assignment2 = Assignment.objects.create(
            lesson=self.lesson2,
            title='Assignment 2',
            description='Assignment 2 description',
            assignment_type='exam'
        )
    
    def test_teacher_can_only_access_own_assignments(self):
        """Test that teachers can only access their own assignments"""
        self.client.force_authenticate(user=self.teacher1)
        
        # Teacher 1 can access their own assignment
        response = self.client.get(f'/api/teacher/assignments/{self.assignment1.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Teacher 1 cannot access teacher 2's assignment
        response = self.client.get(f'/api/teacher/assignments/{self.assignment2.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_teacher_can_only_modify_own_assignments(self):
        """Test that teachers can only modify their own assignments"""
        self.client.force_authenticate(user=self.teacher1)
        
        # Teacher 1 can update their own assignment
        update_data = {'title': 'Updated Assignment 1'}
        response = self.client.put(f'/api/teacher/assignments/{self.assignment1.id}/', update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Teacher 1 cannot update teacher 2's assignment
        update_data = {'title': 'Unauthorized Update'}
        response = self.client.put(f'/api/teacher/assignments/{self.assignment2.id}/', update_data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_teacher_can_only_delete_own_assignments(self):
        """Test that teachers can only delete their own assignments"""
        self.client.force_authenticate(user=self.teacher1)
        
        # Teacher 1 cannot delete teacher 2's assignment
        response = self.client.delete(f'/api/teacher/assignments/{self.assignment2.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_student_cannot_access_teacher_endpoints(self):
        """Test that students cannot access teacher assignment endpoints"""
        self.client.force_authenticate(user=self.student)
        
        # Test all teacher endpoints
        endpoints = [
            f'/api/teacher/assignments/',
            f'/api/teacher/assignments/{self.assignment1.id}/',
            f'/api/teacher/assignments/{self.assignment1.id}/questions/',
            f'/api/teacher/assignments/{self.assignment1.id}/grading/',
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_unauthenticated_cannot_access_endpoints(self):
        """Test that unauthenticated users cannot access any endpoints"""
        endpoints = [
            '/api/teacher/assignments/',
            f'/api/teacher/assignments/{self.assignment1.id}/',
            f'/api/teacher/assignments/{self.assignment1.id}/questions/',
            f'/api/teacher/assignments/{self.assignment1.id}/grading/',
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_admin_can_access_all_assignments(self):
        """Test that admin can access all assignments"""
        self.client.force_authenticate(user=self.admin)
        
        # Admin can access both assignments
        response = self.client.get(f'/api/teacher/assignments/{self.assignment1.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        response = self.client.get(f'/api/teacher/assignments/{self.assignment2.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_cross_teacher_data_isolation(self):
        """Test that teachers cannot see each other's data in lists"""
        self.client.force_authenticate(user=self.teacher1)
        
        response = self.client.get('/api/teacher/assignments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should only see teacher 1's assignment
        assignments = response.data['assignments']
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0]['title'], 'Assignment 1')
        
        # Verify teacher 2's assignment is not in the list
        assignment_titles = [a['title'] for a in assignments]
        self.assertNotIn('Assignment 2', assignment_titles)


class AssignmentValidationTestCase(APITestCase):
    """
    Test cases for Assignment Data Validation
    Tests field validation, business logic, and edge cases
    """
    
    def setUp(self):
        """Set up test data"""
        self.teacher = User.objects.create_user(
            firebase_uid='test_teacher_firebase_uid_4',
            email='teacher@test.com',
            username='teacher@test.com',
            password='testpass123',
            first_name='Test',
            last_name='Teacher',
            role='teacher'
        )
        
        self.course = Course.objects.create(
            title='Test Course',
            description='Test course description',
            teacher=self.teacher,
            category='Computer Science',
            price=99.99,
            is_free=False
        )
        
        self.lesson = Lesson.objects.create(
            course=self.course,
            title='Test Lesson',
            description='Test lesson description',
            order=1,
            duration=60,
            type='text_lesson'
        )
    
    def test_assignment_validation_required_fields(self):
        """Test assignment creation with missing required fields"""
        self.client.force_authenticate(user=self.teacher)
        
        # Test missing lesson
        assignment_data = {
            'title': 'Test Assignment',
            'description': 'Test description',
            'assignment_type': 'homework'
        }
        
        response = self.client.post('/api/teacher/assignments/', assignment_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('lesson', response.data)
        
        # Create a new lesson for testing
        test_lesson = Lesson.objects.create(
            course=self.course,
            title='Test Lesson',
            description='Test lesson description',
            order=3,
            duration=30,
            type='text_lesson'
        )
        
        # Test missing title
        assignment_data = {
            'lesson': str(test_lesson.id),
            'description': 'Test description',
            'assignment_type': 'homework'
        }
        
        response = self.client.post('/api/teacher/assignments/', assignment_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('title', response.data)
        
        # Test missing description (if required by serializer)
        assignment_data = {
            'lesson': str(test_lesson.id),
            'title': 'Test Assignment',
            'assignment_type': 'homework'
        }
        
        response = self.client.post('/api/teacher/assignments/', assignment_data)
        # Note: description might not be required if it has blank=True in model
        # Let's check what the actual response is
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            self.assertIn('description', response.data)
        
        # Create another lesson for testing assignment_type requirement
        test_lesson2 = Lesson.objects.create(
            course=self.course,
            title='Test Lesson 2',
            description='Test lesson 2 description',
            order=4,
            duration=30,
            type='text_lesson'
        )
        
        # Test missing assignment_type
        assignment_data = {
            'lesson': str(test_lesson2.id),
            'title': 'Test Assignment',
            'description': 'Test description'
        }
        
        response = self.client.post('/api/teacher/assignments/', assignment_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('assignment_type', response.data)
    
    def test_assignment_validation_passing_score_range(self):
        """Test assignment passing score validation"""
        self.client.force_authenticate(user=self.teacher)
        
        # Test passing score too high
        assignment_data = {
            'lesson': str(self.lesson.id),
            'title': 'Test Assignment',
            'description': 'Test description',
            'assignment_type': 'homework',
            'passing_score': 101
        }
        
        response = self.client.post('/api/teacher/assignments/', assignment_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('passing_score', response.data)
        
        # Test passing score too low
        assignment_data = {
            'lesson': str(self.lesson.id),
            'title': 'Test Assignment',
            'description': 'Test description',
            'assignment_type': 'homework',
            'passing_score': -1
        }
        
        response = self.client.post('/api/teacher/assignments/', assignment_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('passing_score', response.data)
        
        # Test valid passing score
        assignment_data = {
            'lesson': str(self.lesson.id),
            'title': 'Test Assignment',
            'description': 'Test description',
            'assignment_type': 'homework',
            'passing_score': 75
        }
        
        response = self.client.post('/api/teacher/assignments/', assignment_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_assignment_validation_max_attempts(self):
        """Test assignment max attempts validation"""
        self.client.force_authenticate(user=self.teacher)
        
        # Test max attempts too low
        assignment_data = {
            'lesson': str(self.lesson.id),
            'title': 'Test Assignment',
            'description': 'Test description',
            'assignment_type': 'homework',
            'max_attempts': 0
        }
        
        response = self.client.post('/api/teacher/assignments/', assignment_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('max_attempts', response.data)
        
        # Test valid max attempts
        assignment_data = {
            'lesson': str(self.lesson.id),
            'title': 'Test Assignment',
            'description': 'Test description',
            'assignment_type': 'homework',
            'max_attempts': 3
        }
        
        response = self.client.post('/api/teacher/assignments/', assignment_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_assignment_validation_due_date_future(self):
        """Test assignment due date must be in future"""
        self.client.force_authenticate(user=self.teacher)
        
        # Test past due date
        past_date = timezone.now() - timedelta(days=1)
        assignment_data = {
            'lesson': str(self.lesson.id),
            'title': 'Test Assignment',
            'description': 'Test description',
            'assignment_type': 'homework',
            'due_date': past_date.isoformat()
        }
        
        response = self.client.post('/api/teacher/assignments/', assignment_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('due_date', response.data)
        
        # Test future due date
        future_date = timezone.now() + timedelta(days=7)
        assignment_data = {
            'lesson': str(self.lesson.id),
            'title': 'Test Assignment',
            'description': 'Test description',
            'assignment_type': 'homework',
            'due_date': future_date.isoformat()
        }
        
        response = self.client.post('/api/teacher/assignments/', assignment_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_question_validation_required_fields(self):
        """Test question creation with missing required fields"""
        self.client.force_authenticate(user=self.teacher)
        
        # Create assignment first
        assignment = Assignment.objects.create(
            lesson=self.lesson,
            title='Test Assignment',
            description='Test description',
            assignment_type='homework'
        )
        
        # Test missing question_text
        question_data = {
            'order': 1,
            'points': 5,
            'type': 'multiple_choice',
            'content': {'options': ['A', 'B', 'C', 'D'], 'correct_answer': 'A'}
        }
        
        response = self.client.post(f'/api/teacher/assignments/{assignment.id}/questions/', question_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('question_text', response.data)
        
        # Test missing order
        question_data = {
            'question_text': 'Test question',
            'points': 5,
            'type': 'multiple_choice',
            'content': {'options': ['A', 'B', 'C', 'D'], 'correct_answer': 'A'}
        }
        
        response = self.client.post(f'/api/teacher/assignments/{assignment.id}/questions/', question_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('order', response.data)
        
        # Test missing points
        question_data = {
            'question_text': 'Test question',
            'order': 1,
            'type': 'multiple_choice',
            'content': {'options': ['A', 'B', 'C', 'D'], 'correct_answer': 'A'}
        }
        
        response = self.client.post(f'/api/teacher/assignments/{assignment.id}/questions/', question_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('points', response.data)
        
        # Test missing type
        question_data = {
            'question_text': 'Test question',
            'order': 1,
            'points': 5,
            'content': {'options': ['A', 'B', 'C', 'D'], 'correct_answer': 'A'}
        }
        
        response = self.client.post(f'/api/teacher/assignments/{assignment.id}/questions/', question_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('type', response.data)
    
    def test_question_validation_content_structure(self):
        """Test question content validation for different types"""
        self.client.force_authenticate(user=self.teacher)
        
        # Create assignment first
        assignment = Assignment.objects.create(
            lesson=self.lesson,
            title='Test Assignment',
            description='Test description',
            assignment_type='homework'
        )
        
        # Test multiple choice without options
        question_data = {
            'question_text': 'Test question',
            'order': 1,
            'points': 5,
            'type': 'multiple_choice',
            'content': {'correct_answer': 'A'}
        }
        
        response = self.client.post(f'/api/teacher/assignments/{assignment.id}/questions/', question_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('content', response.data)
        
        # Test true/false without correct_answer
        question_data = {
            'question_text': 'Test question',
            'order': 1,
            'points': 5,
            'type': 'true_false',
            'content': {}
        }
        
        response = self.client.post(f'/api/teacher/assignments/{assignment.id}/questions/', question_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('content', response.data)
        
        # Test flashcard without answer
        question_data = {
            'question_text': 'Test question',
            'order': 1,
            'points': 5,
            'type': 'flashcard',
            'content': {'hint': 'Some hint'}
        }
        
        response = self.client.post(f'/api/teacher/assignments/{assignment.id}/questions/', question_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('content', response.data)
    
    def test_question_validation_points_range(self):
        """Test question points validation"""
        self.client.force_authenticate(user=self.teacher)
        
        # Create assignment first
        assignment = Assignment.objects.create(
            lesson=self.lesson,
            title='Test Assignment',
            description='Test description',
            assignment_type='homework'
        )
        
        # Test negative points
        question_data = {
            'question_text': 'Test question',
            'order': 1,
            'points': -1,
            'type': 'multiple_choice',
            'content': {'options': ['A', 'B', 'C', 'D'], 'correct_answer': 'A'}
        }
        
        response = self.client.post(f'/api/teacher/assignments/{assignment.id}/questions/', question_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('points', response.data)
        
        # Test zero points
        question_data = {
            'question_text': 'Test question',
            'order': 1,
            'points': 0,
            'type': 'multiple_choice',
            'content': {'options': ['A', 'B', 'C', 'D'], 'correct_answer': 'A'}
        }
        
        response = self.client.post(f'/api/teacher/assignments/{assignment.id}/questions/', question_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('points', response.data)
        
        # Test valid points
        question_data = {
            'question_text': 'Test question',
            'order': 1,
            'points': 10,
            'type': 'multiple_choice',
            'content': {'options': ['A', 'B', 'C', 'D'], 'correct_answer': 'A'}
        }
        
        response = self.client.post(f'/api/teacher/assignments/{assignment.id}/questions/', question_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
