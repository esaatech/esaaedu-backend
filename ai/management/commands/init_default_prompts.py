"""
Management command to initialize default AI prompts in the database
Run: python manage.py init_default_prompts
"""
from django.core.management.base import BaseCommand
from ai.models import AIPrompt
from ai.prompts import get_course_categories, format_categories_list


class Command(BaseCommand):
    help = 'Initialize default AI prompts in the database (idempotent - safe to run multiple times)'

    def handle(self, *args, **options):
        self.stdout.write('Initializing default AI prompts...')
        
        # Get categories from database (will create "Others" if no categories exist)
        categories = get_course_categories()
        categories_list = format_categories_list()
        
        # Default schema (will be updated with categories at runtime)
        default_schema = {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Course title (max 200 characters)",
                    "maxLength": 200
                },
                "short_description": {
                    "type": "string",
                    "description": "Brief description that appears on course cards (2-3 sentences)"
                },
                "detailed_description": {
                    "type": "string",
                    "description": "Detailed description for the course page (paragraphs explaining the course)"
                },
                "category": {
                    "type": "string",
                    "description": f"Course category. Must be one of: {', '.join(categories)}. If no category matches exactly, use 'Others'."
                }
            },
            "required": ["title", "short_description", "detailed_description", "category"]
        }
        
        # Default system instruction
        default_system_instruction = """You are an expert educational content creator for children's courses. 
Your role is to create engaging, age-appropriate course proposals that excite students and clearly communicate learning outcomes.

Guidelines:
- Course titles should be clear, engaging, and descriptive (under 200 characters)
- Short descriptions should be compelling and informative (2-3 sentences)
- Detailed descriptions should thoroughly explain the course value and learning outcomes (2-3 paragraphs)
- Categories: Choose from the available categories list if one matches. If none match exactly, use the closest related category. If absolutely no category fits, use "Others".
- All content should be age-appropriate and motivating
- Always return valid JSON matching the exact schema provided

Available Categories:
{available_categories}"""
        
        # Default prompt template
        default_prompt_template = """You are an expert educational content creator specializing in creating engaging courses for children.

User Request: {user_request}{context}

Please generate a complete course proposal with the following:
1. An engaging, clear course title (under 200 characters)
2. A short description (2-3 sentences) that will appear on course cards - make it catchy and informative
3. A detailed description (2-3 paragraphs) for the course page that explains what students will learn, why it's valuable, and what makes it exciting
4. An appropriate category from the available categories list below

Available Categories (choose the best match):
{available_categories_list}

Category Selection Guidelines:
- Choose the category that best matches the course topic from the list above
- If multiple categories could fit, choose the most specific one
- If none match exactly, choose the closest related category
- If absolutely no category is appropriate, use "Others"

Make the course description:
- Age-appropriate and engaging for the target audience
- Clear about learning outcomes
- Exciting and motivating
- Professional yet fun

Return your response as valid JSON matching the required schema."""
        
        # Course Generation Prompt
        prompt, created = AIPrompt.objects.get_or_create(
            prompt_type='course_generation',
            defaults={
                'system_instruction': default_system_instruction.format(
                    available_categories=categories_list
                ),
                'prompt_template': default_prompt_template,
                'output_schema': default_schema,
                'schema_description': f"""Expected output:
{{
  "title": "Course title (max 200 chars)",
  "short_description": "Brief 2-3 sentence description for course cards",
  "detailed_description": "Detailed 2-3 paragraph description for course page",
  "category": "One of: {', '.join(categories)}. Use 'Others' if no match."
}}""",
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS('✓ Created default course_generation prompt')
            )
        else:
            self.stdout.write(
                self.style.WARNING('→ course_generation prompt already exists (skipped)')
            )
            # Update if it's inactive
            if not prompt.is_active:
                prompt.is_active = True
                prompt.save()
                self.stdout.write(
                    self.style.SUCCESS('✓ Reactivated course_generation prompt')
                )
        
        self.stdout.write(
            self.style.SUCCESS('\n✓ Default prompts initialized!')
        )
        self.stdout.write(
            self.style.SUCCESS('You can now edit these prompts in Django Admin under AI > AI Prompts')
        )

