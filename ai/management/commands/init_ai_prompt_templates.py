"""
Management command to initialize default AI Prompt Templates in the database
Run: python manage.py init_ai_prompt_templates

This command creates AIPromptTemplate entries for all AI services:
- course_detail: Course basic information generation
- course_introduction: Course introduction generation
- course_lessons: Course lessons generation
- quiz_generation: Quiz generation from materials
- assignment_generation: Assignment generation from materials
- assignment_grading: AI-powered assignment grading with feedback and correct answer generation
"""
from django.core.management.base import BaseCommand
from ai.models import AIPromptTemplate


class Command(BaseCommand):
    help = 'Initialize default AI Prompt Templates for all services (idempotent - safe to run multiple times)'

    def handle(self, *args, **options):
        self.stdout.write('Initializing AI Prompt Templates...')
        
        # Define all prompt templates
        templates = [
            {
                'name': 'course_detail',
                'display_name': 'Course Detail Generation',
                'description': 'Generate basic course information: title, short description, detailed description, category, and difficulty level',
                'default_system_instruction': """You are an expert course creator specializing in educational content for children.
Generate comprehensive course details that are engaging, clear, and informative.
Focus on creating value for students and highlighting what makes the course unique.

Guidelines:
- Course titles should be clear, engaging, and descriptive
- Short descriptions should be compelling and informative (1-2 sentences)
- Detailed descriptions should thoroughly explain the course value and learning outcomes (multiple paragraphs)
- Categories should be appropriate and match existing course categories
- Difficulty levels should accurately reflect the course content (beginner, intermediate, or advanced)
- All content should be age-appropriate and motivating
- Ensure all information is accurate, engaging, and appropriate for the target audience""",
                'model_name': 'gemini-2.0-flash-001',
                'temperature': 0.7,
                'max_tokens': None
            },
            {
                'name': 'course_introduction',
                'display_name': 'Course Introduction Generation',
                'description': 'Generate comprehensive course introduction details including overview, learning objectives, prerequisites, duration, and value propositions',
                'default_system_instruction': """You are an expert course creator specializing in educational content.
Generate comprehensive course introductions that are engaging, clear, and informative.
Focus on creating value for students and highlighting what makes the course unique.
Ensure the introduction includes detailed overview, learning objectives, prerequisites, duration, sessions per week, total projects, max students, and value propositions.""",
                'model_name': 'gemini-2.0-flash-001',
                'temperature': 0.7,
                'max_tokens': None
            },
            {
                'name': 'course_lessons',
                'display_name': 'Course Lessons Generation',
                'description': 'Generate lesson outlines for a course organized in cumulative/scaffolded order',
                'default_system_instruction': """You are an expert educational content creator specializing in curriculum design.
Generate comprehensive lesson outlines that follow a cumulative/scaffolded learning approach.
Each lesson should build upon previous lessons, gradually increasing in complexity.

Guidelines:
- Organize lessons in logical, progressive order
- Each lesson should have clear learning objectives
- Lessons should scaffold knowledge and skills
- Include appropriate lesson types (live_class, video_audio, text_lesson)
- Set realistic durations based on content complexity
- Ensure lessons align with course duration and sessions per week""",
                'model_name': 'gemini-2.0-flash-001',
                'temperature': 0.7,
                'max_tokens': None
            },
            {
                'name': 'quiz_generation',
                'display_name': 'Quiz Generation',
                'description': 'Generate quiz questions from lesson materials',
                'default_system_instruction': """You are an expert quiz creator specializing in educational content.
Generate comprehensive quiz questions that test understanding of the lesson material.
Create a mix of multiple choice and true/false questions with clear correct answers.

Guidelines:
- Questions should test understanding, not just memorization
- Multiple choice questions should have 4 clear options
- True/false questions should be unambiguous
- Include helpful explanations for each question
- Ensure questions cover different aspects of the lesson content
- Questions should be appropriate for the target age group""",
                'model_name': 'gemini-2.0-flash-001',
                'temperature': 0.7,
                'max_tokens': None
            },
            {
                'name': 'assignment_generation',
                'display_name': 'Assignment Generation',
                'description': 'Generate assignment questions from lesson materials',
                'default_system_instruction': """You are an expert assignment creator specializing in educational content.
Generate comprehensive assignment questions that require students to demonstrate understanding and application of lesson material.
Create a mix of essay questions, fill-in-the-blank, and short answer questions with clear requirements.

Guidelines:
- Essay questions should require critical thinking and application
- Fill-in-the-blank questions should test key concepts
- Short answer questions should be specific and answerable
- Provide clear requirements and rubrics where appropriate
- Ensure questions align with learning objectives
- Questions should be appropriate for the target age group""",
                'model_name': 'gemini-2.0-flash-001',
                'temperature': 0.7,
                'max_tokens': None
            },
            {
                'name': 'assignment_grading',
                'display_name': 'Assignment Grading',
                'description': 'AI-powered grading of student assignment submissions with feedback and correct answer generation',
                'default_system_instruction': """You are an expert educational grader writing feedback directly to students. Your role is to evaluate student answers with:
- Focus on understanding and ideas, not just correctness
- Provide constructive feedback written in second person (use 'you' and 'your') - write as if you are the teacher speaking directly to the student
- Write feedback naturally and conversationally - avoid formal prefixes like "Reasoning:", "Feedback:", or "The answer is..."
- Use phrases like "Your answer..." or "You got..." instead of "The answer is..." or "The student's answer..."
- Award partial credit when appropriate
- Consider context and meaning

IMPORTANT: After providing feedback, you must also generate a correct answer or model answer:
- For questions with rigid correct answers (factual, mathematical, etc.): Provide the standard correct answer
- For open-ended questions (essays, creative responses, etc.): Frame the correct answer around the student's response when appropriate. Use the student's chosen topic/approach but demonstrate the correct format, structure, and completeness expected
- The correct answer should demonstrate what a complete, high-quality response looks like
- It will be shown to the student as a correction/reference, so make it clear and educational

If you cannot grade the question due to unclear question, unclear answer, or insufficient information, award 0 points and provide feedback explaining why grading is not possible.""",
                'model_name': 'gemini-2.0-flash-001',
                'temperature': 0.3,
                'max_tokens': None
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for template_data in templates:
            template, created = AIPromptTemplate.objects.get_or_create(
                name=template_data['name'],
                defaults={
                    'display_name': template_data['display_name'],
                    'description': template_data['description'],
                    'default_system_instruction': template_data['default_system_instruction'],
                    'model_name': template_data['model_name'],
                    'temperature': template_data['temperature'],
                    'max_tokens': template_data['max_tokens'],
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created: {template_data["display_name"]}')
                )
            else:
                # Update if system instruction is different or template is inactive
                updated = False
                if template.default_system_instruction != template_data['default_system_instruction']:
                    template.default_system_instruction = template_data['default_system_instruction']
                    updated = True
                if not template.is_active:
                    template.is_active = True
                    updated = True
                if updated:
                    template.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'→ Updated: {template_data["display_name"]}')
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f'→ Already exists: {template_data["display_name"]}')
                    )
        
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(f'\n✓ Initialization complete!')
        )
        self.stdout.write(f'  Created: {created_count}')
        self.stdout.write(f'  Updated: {updated_count}')
        self.stdout.write(f'  Total: {len(templates)}')
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS('You can now edit these templates in Django Admin under AI > AI Prompt Templates')
        )

