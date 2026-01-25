from django.test import TestCase
from .models import Program


class ProgramModelTest(TestCase):
    """Test cases for Program model."""
    
    def test_slug_auto_generation(self):
        """Test that slug is auto-generated from name."""
        program = Program.objects.create(
            name="Math Program",
            description="Test description",
            category="Mathematics"
        )
        self.assertEqual(program.slug, "math-program")
    
    def test_slug_uniqueness(self):
        """Test that duplicate slugs are handled."""
        Program.objects.create(
            name="Math Program",
            description="Test",
            category="Mathematics"
        )
        program2 = Program.objects.create(
            name="Math Program",
            description="Test 2",
            category="Mathematics"
        )
        self.assertNotEqual(program2.slug, "math-program")
        self.assertTrue(program2.slug.startswith("math-program"))
    
    def test_category_or_courses_required(self):
        """Test that either category or courses must be set."""
        with self.assertRaises(Exception):
            Program.objects.create(
                name="Test Program",
                description="Test"
            )


