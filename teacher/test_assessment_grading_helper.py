"""Unit tests for assessment hybrid grading (deterministic paths)."""
from django.test import SimpleTestCase

from teacher.assessment_grading_helper import (
    try_deterministic_grade,
    run_assessment_hybrid_grading,
)


class DeterministicAssessmentGradingTests(SimpleTestCase):
    def test_multiple_choice_correct(self):
        g = try_deterministic_grade(
            "multiple_choice",
            {"correct_answer": "Paris"},
            "Paris",
            5,
        )
        self.assertIsNotNone(g)
        assert g is not None
        self.assertEqual(g["points_earned"], 5.0)

    def test_multiple_choice_wrong(self):
        g = try_deterministic_grade(
            "multiple_choice",
            {"correct_answer": "Paris"},
            "London",
            5,
        )
        self.assertIsNotNone(g)
        assert g is not None
        self.assertEqual(g["points_earned"], 0.0)

    def test_true_false(self):
        g = try_deterministic_grade("true_false", {"correct_answer": "true"}, "true", 2)
        self.assertIsNotNone(g)
        assert g is not None
        self.assertEqual(g["points_earned"], 2.0)

    def test_short_answer_keyed(self):
        g = try_deterministic_grade(
            "short_answer",
            {"correct_answer": "photosynthesis", "accept_variations": True},
            "Photosynthesis",
            3,
        )
        self.assertIsNotNone(g)
        assert g is not None
        self.assertEqual(g["points_earned"], 3.0)

    def test_short_answer_no_key_returns_none(self):
        g = try_deterministic_grade("short_answer", {}, "anything", 3)
        self.assertIsNone(g)

    def test_fill_blank_partial(self):
        g = try_deterministic_grade(
            "fill_blank",
            {"correct_answers": {"0": "cat", "1": "dog"}},
            "cat,fish",
            4,
        )
        self.assertIsNotNone(g)
        assert g is not None
        self.assertEqual(g["points_earned"], 2.0)

    def test_ordering_partial(self):
        g = try_deterministic_grade(
            "ordering",
            {"correct_order": ["first", "second", "third"]},
            ["first", "third", "second"],
            6,
        )
        self.assertIsNotNone(g)
        assert g is not None
        self.assertEqual(g["points_earned"], 2.0)

    def test_matching_partial(self):
        g = try_deterministic_grade(
            "matching",
            {
                "pairs": [
                    {"left": "A", "right": "1"},
                    {"left": "B", "right": "2"},
                ]
            },
            [{"left": "A", "right": "1"}, {"left": "B", "right": "3"}],
            4,
        )
        self.assertIsNotNone(g)
        assert g is not None
        self.assertEqual(g["points_earned"], 2.0)


class HybridBatchOrderingTests(SimpleTestCase):
    def test_all_deterministic_no_llm(self):
        payload = [
            {
                "question_id": "q1",
                "question_type": "multiple_choice",
                "question_text": "Capital of France?",
                "student_answer": "Paris",
                "points_possible": 2,
                "content": {"correct_answer": "Paris"},
            },
            {
                "question_id": "q2",
                "question_type": "true_false",
                "question_text": "Sky is blue",
                "student_answer": "true",
                "points_possible": 1,
                "content": {"correct_answer": "true"},
            },
        ]
        out = run_assessment_hybrid_grading(payload, None)
        self.assertEqual(len(out["grades"]), 2)
        self.assertEqual(out["total_score"], 3.0)
        self.assertEqual(out["total_possible"], 3.0)
        ids = [g["question_id"] for g in out["grades"]]
        self.assertEqual(ids, ["q1", "q2"])
