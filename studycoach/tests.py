from django.test import SimpleTestCase

from studycoach.services.deck_generator import (
    FALLBACK_EXPLANATION,
    attach_card_sources,
    format_page_catalog_for_prompt,
    resolve_card_source,
)


CATALOG = [
    {
        "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "material_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "page": 2,
        "title": "Subtracting fractions",
        "excerpt": "Keep the denominator the same.",
    },
    {
        "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
        "material_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "page": 3,
        "title": "Adding fractions",
        "excerpt": "",
    },
]


class CardSourceResolutionTests(SimpleTestCase):
    def test_resolves_catalog_id(self):
        source = resolve_card_source(
            {"source_page_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"},
            CATALOG,
        )
        self.assertEqual(source["page"], 2)
        self.assertEqual(source["title"], "Subtracting fractions")
        self.assertEqual(source["material_id"], "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    def test_drops_invented_id(self):
        self.assertIsNone(
            resolve_card_source({"source_page_id": "not-a-real-id"}, CATALOG)
        )

    def test_unique_page_number_fallback(self):
        source = resolve_card_source({"source_page_id": "3"}, CATALOG)
        self.assertEqual(source["title"], "Adding fractions")

    def test_single_page_catalog_defaults(self):
        source = resolve_card_source({}, CATALOG[:1])
        self.assertEqual(source["page"], 2)

    def test_attach_strips_source_page_id_and_fills_explanation(self):
        cards = attach_card_sources(
            [
                {
                    "prompt": "Subtract",
                    "source_page_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                }
            ],
            CATALOG,
        )
        self.assertNotIn("source_page_id", cards[0])
        self.assertEqual(cards[0]["source"]["page"], 2)
        self.assertEqual(cards[0]["explanation"], FALLBACK_EXPLANATION)

    def test_catalog_prompt_includes_ids_not_urls(self):
        text = format_page_catalog_for_prompt(CATALOG)
        self.assertIn("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", text)
        self.assertNotIn("http", text)
        self.assertNotIn("/dashboard", text)


from unittest.mock import MagicMock, patch

from studycoach.services.grading import (
    StudyCoachGradeError,
    grade_study_card,
)


class StudyCoachGradingTests(SimpleTestCase):
    def test_mcq_uses_answer_key(self):
        card = {
            "question_type": "multiple_choice",
            "prompt": "Pick one",
            "options": ["A", "B"],
            "answer": "A",
        }
        correct, meta = grade_study_card(card, "A")
        self.assertTrue(correct)
        self.assertEqual(meta["graded_by"], "key")

    def test_numeric_short_answer_uses_key(self):
        card = {
            "question_type": "short_answer",
            "prompt": "Add",
            "answer": "77",
        }
        correct, meta = grade_study_card(card, "77")
        self.assertTrue(correct)
        self.assertEqual(meta["graded_by"], "key")

    def test_blank_short_answer_skips_ai(self):
        card = {
            "question_type": "short_answer",
            "prompt": "What is current?",
            "answer": "The flow of charge",
        }
        correct, meta = grade_study_card(card, "  ")
        self.assertFalse(correct)
        self.assertEqual(meta["graded_by"], "skipped")

    @patch("studycoach.services.grading.generate_study_coach_grade")
    def test_paraphrase_short_answer_uses_ai(self, mock_grade):
        mock_grade.return_value = {
            "success": True,
            "result": {"correct": True, "feedback": "You described the idea well."},
            "provider": "gemini",
            "model_id": "gemini-2.5-flash-lite",
        }
        card = {
            "id": "c1",
            "question_type": "short_answer",
            "prompt": "What is electric current?",
            "answer": "The flow of charge through a conductor over time.",
            "explanation": "Current is charge flowing.",
        }
        correct, meta = grade_study_card(
            card,
            "electric current is generated when electrons flow",
            lesson=MagicMock(title="Electricity"),
        )
        self.assertTrue(correct)
        self.assertEqual(meta["graded_by"], "ai")
        mock_grade.assert_called_once()

    @patch("studycoach.services.grading.generate_study_coach_grade")
    def test_ai_error_does_not_mark_wrong(self, mock_grade):
        mock_grade.return_value = {
            "success": False,
            "error": "rate limited",
            "error_code": "rate_limited",
            "result": None,
        }
        card = {
            "question_type": "short_answer",
            "prompt": "What is current?",
            "answer": "The flow of charge",
        }
        with self.assertRaises(StudyCoachGradeError):
            grade_study_card(card, "electrons moving through a wire")
