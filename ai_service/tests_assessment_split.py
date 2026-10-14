"""Question totals are split across lessons before any model call."""
from django.test import SimpleTestCase

from ai_service.assessment_split import questions_per_lesson, split_type_counts


class _Lesson:
    def __init__(self, order):
        self.order = order


class AssessmentSplitTests(SimpleTestCase):
    def test_extras_go_to_later_lessons(self):
        self.assertEqual(questions_per_lesson(4, 6), [1, 1, 2, 2])

    def test_fewer_questions_than_lessons_keeps_the_later_ones(self):
        self.assertEqual(questions_per_lesson(4, 2), [0, 0, 1, 1])

    def test_type_counts_still_add_up(self):
        lessons = [_Lesson(index) for index in range(1, 5)]
        totals = {
            "multiple_choice": 10,
            "true_false": 3,
            "fill_blank": 0,
            "short_answer": 0,
            "essay": 5,
            "code": 2,
        }
        plans = split_type_counts(lessons, totals)
        self.assertEqual(sum(plan["total"] for plan in plans), 20)
        self.assertEqual([plan["total"] for plan in plans], [5, 5, 5, 5])
        for key, expected in totals.items():
            self.assertEqual(sum(plan["counts"][key] for plan in plans), expected)
        self.assertTrue(all(sum(plan["counts"].values()) == plan["total"] for plan in plans))
