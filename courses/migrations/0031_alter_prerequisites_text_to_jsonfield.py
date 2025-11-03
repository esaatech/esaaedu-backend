# Generated migration to convert prerequisites_text from TextField to JSONField

from django.db import migrations, models
import json


def convert_text_to_json(apps, schema_editor):
    """
    Final cleanup: Ensure all prerequisites_text values are proper JSON arrays.
    This runs AFTER the column has been converted to jsonb.
    """
    Course = apps.get_model('courses', 'Course')
    db_alias = schema_editor.connection.alias
    
    # Get all courses and ensure prerequisites_text is a list
    courses = Course.objects.using(db_alias).all()
    
    for course in courses:
        current_value = course.prerequisites_text
        
        # Ensure it's always a list
        if not isinstance(current_value, list):
            if current_value is None:
                new_value = []
            elif isinstance(current_value, str):
                try:
                    parsed = json.loads(current_value)
                    new_value = parsed if isinstance(parsed, list) else [parsed] if parsed else []
                except (json.JSONDecodeError, TypeError):
                    new_value = [current_value] if current_value.strip() else []
            else:
                new_value = []
        else:
            new_value = current_value
        
        # Update if needed
        if new_value != current_value:
            Course.objects.using(db_alias).filter(id=course.id).update(prerequisites_text=new_value)


def convert_json_to_text(apps, schema_editor):
    """
    Reverse migration: convert JSON array back to string.
    Join array items with commas or take first item.
    """
    Course = apps.get_model('courses', 'Course')
    db_alias = schema_editor.connection.alias
    
    courses = Course.objects.using(db_alias).all()
    
    for course in courses:
        # Get the raw JSON value from database
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                "SELECT prerequisites_text FROM courses_course WHERE id = %s",
                [course.id]
            )
            row = cursor.fetchone()
            raw_value = row[0] if row else None
        
        # Convert JSON array to string
        if raw_value:
            try:
                if isinstance(raw_value, str):
                    parsed = json.loads(raw_value)
                else:
                    parsed = raw_value
                
                if isinstance(parsed, list):
                    # Join list items with comma and space
                    new_value = ', '.join(str(item) for item in parsed) if parsed else ''
                else:
                    new_value = str(parsed)
            except (json.JSONDecodeError, TypeError):
                new_value = str(raw_value)
        else:
            new_value = ''
        
        # Update directly in database
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                "UPDATE courses_course SET prerequisites_text = %s WHERE id = %s",
                [new_value, course.id]
            )


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0030_alter_lessonmaterial_material_type'),
    ]

    operations = [
        # Step 1: Change the column type from text to jsonb with proper conversion
        # This uses PostgreSQL's USING clause to convert text to jsonb on-the-fly
        migrations.RunSQL(
            sql="""
                ALTER TABLE courses_course 
                ALTER COLUMN prerequisites_text TYPE jsonb 
                USING CASE
                    WHEN prerequisites_text IS NULL OR prerequisites_text = '' THEN '[]'::jsonb
                    WHEN prerequisites_text ~ '^\\s*\\[' THEN prerequisites_text::jsonb
                    ELSE jsonb_build_array(prerequisites_text)
                END;
            """,
            reverse_sql="""
                ALTER TABLE courses_course 
                ALTER COLUMN prerequisites_text TYPE text 
                USING CASE
                    WHEN prerequisites_text::jsonb = '[]'::jsonb THEN ''
                    WHEN jsonb_array_length(prerequisites_text::jsonb) = 1 THEN prerequisites_text::jsonb->>0
                    ELSE array_to_string(ARRAY(SELECT jsonb_array_elements_text(prerequisites_text::jsonb)), ', ')
                END;
            """,
        ),
        
        # Step 2: Update the Django model field definition
        migrations.AlterField(
            model_name='course',
            name='prerequisites_text',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='List of prerequisites as JSON array'
            ),
        ),
        
        # Step 3: Final cleanup to ensure all values are proper arrays
        migrations.RunPython(convert_text_to_json, convert_json_to_text),
    ]

