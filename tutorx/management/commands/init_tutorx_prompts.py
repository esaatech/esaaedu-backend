"""
Management command to initialize default TutorX Block Action Configs and User Instructions Defaults in the database
Run: python manage.py init_tutorx_prompts

This command creates:
1. TutorXBlockActionConfig entries for all block action types (system instructions)
2. TutorXUserInstructionsDefaults entries for all block action types (default user instructions)

Action types:
- explain_more: Expand on block content with more detail
- give_examples: Generate examples related to block content
- simplify: Make content easier to understand
- summarize: Create a concise summary
- generate_questions: Create questions based on block content

This is idempotent - safe to run multiple times.
"""
from django.core.management.base import BaseCommand
from tutorx.models import TutorXBlockActionConfig, TutorXUserInstructionsDefaults


class Command(BaseCommand):
    help = 'Initialize default TutorX Block Action Configs (system instructions) and User Instructions Defaults - idempotent'

    def handle(self, *args, **options):
        self.stdout.write('Initializing TutorX Block Action Configs and User Instructions Defaults...')
        self.stdout.write('')
        
        # Define all block action configs with default system instructions
        configs = [
            {
                'action_type': 'explain_more',
                'display_name': 'Explain More',
                'description': 'Generate expanded explanations for content blocks',
                'system_instruction': """You are an expert educational assistant helping students understand content better.
Your role is to provide clear, detailed explanations that help learners grasp concepts more deeply.
Always maintain an educational, supportive tone.

Guidelines:
- Expand on the key concepts in the block content
- Provide additional context and background information
- Use clear, accessible language appropriate for the target audience
- Help students understand the "why" and "how", not just the "what"
- Maintain educational value and accuracy
- Break down complex ideas into understandable parts
- Use examples and analogies when helpful
- Keep explanations engaging and motivating""",
                'default_user_prompt': """Please provide a detailed, expanded explanation of the following block content:

{block_content}

Provide a comprehensive explanation that:
- Expands on the key concepts
- Provides additional context and background
- Uses clear, accessible language
- Helps students understand the "why" and "how", not just the "what"
- Maintains educational value and accuracy

Return only the expanded explanation text, no additional formatting."""
            },
            {
                'action_type': 'give_examples',
                'display_name': 'Give Examples',
                'description': 'Generate examples related to block content',
                'system_instruction': """You are an expert educational assistant helping students learn through examples.
Your role is to provide clear, relevant examples that illustrate concepts effectively.
Always maintain an educational, supportive tone.

Guidelines:
- Generate examples that are directly relevant to the block content
- Help illustrate the key concepts clearly
- Make examples clear and easy to understand
- Ensure examples are appropriate for educational purposes
- Vary examples in complexity or approach when multiple examples are requested
- Use real-world scenarios when possible
- Make examples relatable to the target audience
- Ensure examples reinforce learning objectives""",
                'default_user_prompt': """Based on the following block content, provide {num_examples} {example_type} examples:

{block_content}

Generate exactly {num_examples} examples that:
- Are directly relevant to the content
- Help illustrate the key concepts
- Are clear and easy to understand
- Are appropriate for educational purposes
- Vary in complexity or approach

Return the examples as a numbered list, one per line."""
            },
            {
                'action_type': 'simplify',
                'display_name': 'Simplify',
                'description': 'Simplify block content to make it easier to understand',
                'system_instruction': """You are an expert educational assistant specializing in making complex content accessible.
Your role is to simplify content while maintaining accuracy and educational value.
Always maintain an educational, supportive tone.

Guidelines:
- Maintain all key information and accuracy
- Use clearer, more accessible language
- Break down complex concepts into simpler parts
- Remove unnecessary complexity without losing meaning
- Adapt language to the target level (beginner, intermediate, advanced)
- Use simpler vocabulary when appropriate
- Explain technical terms in plain language
- Structure content for easier comprehension
- Keep the educational value intact""",
                'default_user_prompt': """Simplify the following block content to make it easier to understand:

{block_content}

Target Level: {target_level}

Provide a simplified version that:
- Maintains all key information and accuracy
- Uses clearer, more accessible language
- Breaks down complex concepts into simpler parts
- Removes unnecessary complexity
- Is appropriate for {target_level} level learners

Return only the simplified content, no additional explanation."""
            },
            {
                'action_type': 'summarize',
                'display_name': 'Summarize',
                'description': 'Create concise summaries of block content',
                'system_instruction': """You are an expert educational assistant specializing in creating clear summaries.
Your role is to distill content into concise, informative summaries.
Always maintain an educational, supportive tone.

Guidelines:
- Capture the main points and key concepts
- Maintain appropriate length (brief, medium, or detailed as requested)
- Preserve educational value
- Keep summaries clear and easy to understand
- Focus on essential information
- Organize information logically
- Ensure summaries are useful for learning and review
- Avoid losing critical information in the summarization process""",
                'default_user_prompt': """Create a {length} summary of the following block content:

{block_content}

Provide a summary that:
- Captures the main points and key concepts
- Is concise and informative
- Maintains educational value
- Is clear and easy to understand

Return only the summary text, no additional formatting."""
            },
            {
                'action_type': 'generate_questions',
                'display_name': 'Generate Questions',
                'description': 'Generate educational questions based on block content',
                'system_instruction': """You are an expert educational assistant specializing in creating educational questions.
Your role is to generate questions that test understanding and promote learning.
Always maintain an educational, supportive tone.

Guidelines:
- Generate questions that test understanding of key concepts
- Ensure questions are appropriate for educational purposes
- Vary question difficulty and type as requested
- Help reinforce learning through well-crafted questions
- Make questions clear and unambiguous
- Cover different aspects of the block content
- Include appropriate question types (multiple choice, short answer, true/false, etc.)
- Ensure questions align with learning objectives
- Create questions that promote critical thinking when appropriate""",
                'default_user_prompt': """Based on the following block content, generate {num_questions} educational questions:

{block_content}

Question Types: {question_types}

Generate questions that:
- Test understanding of key concepts
- Are appropriate for educational purposes
- Vary in difficulty and type
- Help reinforce learning
- Are clear and unambiguous

Return the questions as a JSON array, where each question has:
- "question": The question text
- "type": Question type (e.g., "multiple_choice", "short_answer", "true_false")
- "difficulty": Difficulty level ("easy", "medium", "hard")

Return ONLY valid JSON, no additional text."""
            }
        ]
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        for config_data in configs:
            action_type = config_data['action_type']
            
            # Check if config already exists
            existing_config = TutorXBlockActionConfig.objects.filter(
                action_type=action_type,
                is_active=True
            ).first()
            
            if existing_config:
                # Check if system instruction or default user prompt has changed
                system_changed = existing_config.system_instruction != config_data['system_instruction']
                new_default_prompt = config_data.get('default_user_prompt', '')
                # Update if prompt is empty OR if it's different
                prompt_changed = (not existing_config.default_user_prompt or 
                                 existing_config.default_user_prompt != new_default_prompt)
                
                if system_changed or prompt_changed:
                    # Create new version (save will auto-increment version if system_instruction changed)
                    if system_changed:
                        existing_config.system_instruction = config_data['system_instruction']
                    if prompt_changed:
                        existing_config.default_user_prompt = new_default_prompt
                    existing_config.description = config_data.get('description', '')
                    existing_config.is_active = True
                    existing_config.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Updated {config_data["display_name"]} (v{existing_config.version})'
                        )
                    )
                else:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'  → {config_data["display_name"]} already exists with same content (skipped)'
                        )
                    )
            else:
                # Create new config
                config = TutorXBlockActionConfig.objects.create(
                    action_type=action_type,
                    display_name=config_data['display_name'],
                    description=config_data.get('description', ''),
                    system_instruction=config_data['system_instruction'],
                    default_user_prompt=config_data.get('default_user_prompt', ''),
                    is_active=True
                )
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ Created {config_data["display_name"]} (v{config.version})'
                    )
                )
        
        # Summary for Block Action Configs
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('TutorX Block Action Configs Summary:'))
        self.stdout.write(self.style.SUCCESS(f'  Created: {created_count}'))
        self.stdout.write(self.style.SUCCESS(f'  Updated: {updated_count}'))
        self.stdout.write(self.style.SUCCESS(f'  Skipped: {skipped_count}'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')
        
        # Now initialize TutorXUserInstructionsDefaults
        self.stdout.write('Initializing TutorX User Instructions Defaults...')
        
        defaults_created_count = 0
        defaults_updated_count = 0
        defaults_skipped_count = 0
        
        for config_data in configs:
            action_type = config_data['action_type']
            default_user_instruction = config_data.get('default_user_prompt', '')
            
            if not default_user_instruction:
                continue  # Skip if no default user instruction
            
            # Check if default already exists
            existing_default = TutorXUserInstructionsDefaults.objects.filter(
                action_type=action_type,
                is_active=True
            ).first()
            
            if existing_default:
                # Check if default_user_instruction has changed
                instruction_changed = existing_default.default_user_instruction != default_user_instruction
                
                if instruction_changed:
                    # Update (save will auto-increment version if default_user_instruction changed)
                    existing_default.default_user_instruction = default_user_instruction
                    existing_default.display_name = config_data['display_name']
                    existing_default.description = config_data.get('description', '')
                    existing_default.is_active = True
                    existing_default.save()
                    defaults_updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Updated {config_data["display_name"]} default (v{existing_default.version})'
                        )
                    )
                else:
                    defaults_skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'  → {config_data["display_name"]} default already exists with same content (skipped)'
                        )
                    )
            else:
                # Create new default
                default = TutorXUserInstructionsDefaults.objects.create(
                    action_type=action_type,
                    display_name=config_data['display_name'],
                    description=config_data.get('description', ''),
                    default_user_instruction=default_user_instruction,
                    is_active=True
                )
                defaults_created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ Created {config_data["display_name"]} default (v{default.version})'
                    )
                )
        
        # Summary for User Instructions Defaults
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('TutorX User Instructions Defaults Summary:'))
        self.stdout.write(self.style.SUCCESS(f'  Created: {defaults_created_count}'))
        self.stdout.write(self.style.SUCCESS(f'  Updated: {defaults_updated_count}'))
        self.stdout.write(self.style.SUCCESS(f'  Skipped: {defaults_skipped_count}'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                '✓ TutorX initialization complete!'
            )
        )
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                'You can now edit these in Django Admin:'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                '  - TutorX > TutorX Block Action Configs (system instructions)'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                '  - TutorX > TutorX User Instructions Defaults (default user instructions)'
            )
        )
        self.stdout.write('')

