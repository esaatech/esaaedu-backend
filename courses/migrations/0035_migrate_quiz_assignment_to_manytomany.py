# Generated migration to convert Quiz and Assignment from OneToOneField to ManyToManyField

from django.db import migrations, models


def migrate_quiz_lessons(apps, schema_editor):
    """
    Migrate existing Quiz.lesson (OneToOne) relationships to Quiz.lessons (ManyToMany)
    This runs AFTER the new ManyToMany field is added but BEFORE the old OneToOneField is removed
    """
    Quiz = apps.get_model('courses', 'Quiz')
    Lesson = apps.get_model('courses', 'Lesson')
    
    # Use raw SQL to access the old lesson_id field since we're in a migration
    from django.db import connection
    with connection.cursor() as cursor:
        # Get all quizzes with their lesson_id
        cursor.execute("SELECT id, lesson_id FROM courses_quiz WHERE lesson_id IS NOT NULL")
        for quiz_id, lesson_id in cursor.fetchall():
            try:
                quiz = Quiz.objects.get(id=quiz_id)
                lesson = Lesson.objects.get(id=lesson_id)
                quiz.lessons.add(lesson)
            except (Quiz.DoesNotExist, Lesson.DoesNotExist):
                continue


def migrate_assignment_lessons(apps, schema_editor):
    """
    Migrate existing Assignment.lesson (OneToOne) relationships to Assignment.lessons (ManyToMany)
    """
    Assignment = apps.get_model('courses', 'Assignment')
    Lesson = apps.get_model('courses', 'Lesson')
    
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, lesson_id FROM courses_assignment WHERE lesson_id IS NOT NULL")
        for assignment_id, lesson_id in cursor.fetchall():
            try:
                assignment = Assignment.objects.get(id=assignment_id)
                lesson = Lesson.objects.get(id=lesson_id)
                assignment.lessons.add(lesson)
            except (Assignment.DoesNotExist, Lesson.DoesNotExist):
                continue


def reverse_migrate_quiz_lessons(apps, schema_editor):
    """
    Reverse migration: Clear ManyToMany relationships
    Note: Cannot restore OneToOneField automatically
    """
    Quiz = apps.get_model('courses', 'Quiz')
    for quiz in Quiz.objects.all():
        quiz.lessons.clear()


def reverse_migrate_assignment_lessons(apps, schema_editor):
    """
    Reverse migration: Clear ManyToMany relationships
    """
    Assignment = apps.get_model('courses', 'Assignment')
    for assignment in Assignment.objects.all():
        assignment.lessons.clear()


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0034_add_transcript_available_to_students'),
    ]

    operations = [
        # Step 1: Add the new ManyToMany fields
        migrations.AddField(
            model_name='quiz',
            name='lessons',
            field=models.ManyToManyField(related_name='quizzes', to='courses.lesson', blank=True),
        ),
        migrations.AddField(
            model_name='assignment',
            name='lessons',
            field=models.ManyToManyField(related_name='assignments', to='courses.lesson', blank=True),
        ),
        # Step 2: Migrate data from old OneToOneField to new ManyToManyField
        migrations.RunPython(migrate_quiz_lessons, reverse_migrate_quiz_lessons),
        migrations.RunPython(migrate_assignment_lessons, reverse_migrate_assignment_lessons),
        # Step 3: Remove old OneToOneField
        migrations.RemoveField(
            model_name='quiz',
            name='lesson',
        ),
        migrations.RemoveField(
            model_name='assignment',
            name='lesson',
        ),
    ]

