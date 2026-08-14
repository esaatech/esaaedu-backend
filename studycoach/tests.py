from django.test import SimpleTestCase

from studycoach.services.card_metadata import (
    FALLBACK_EXPLANATION,
    attach_card_metadata,
    attach_card_sources,
    format_content_catalog_for_prompt,
    format_page_catalog_for_prompt,
    normalize_difficulty,
    normalize_stored_card,
    resolve_card_source,
    resolve_card_sources,
)


CATALOG = [
    {
        "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "kind": "page",
        "material_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "page": 2,
        "title": "Subtracting fractions",
        "excerpt": "Keep the denominator the same.",
    },
    {
        "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
        "kind": "page",
        "material_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "page": 3,
        "title": "Adding fractions",
        "excerpt": "",
    },
    {
        "id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
        "kind": "video",
        "material_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
        "title": "Fractions intro",
        "excerpt": "",
    },
    {
        "id": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        "kind": "pdf",
        "material_id": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        "title": "Fractions worksheet",
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
        self.assertEqual(
            resolve_card_sources({"source_ids": ["not-a-real-id"]}, CATALOG),
            [],
        )

    def test_unique_page_number_fallback(self):
        source = resolve_card_source({"source_page_id": "3"}, CATALOG)
        self.assertEqual(source["title"], "Adding fractions")

    def test_single_page_catalog_defaults(self):
        source = resolve_card_source({}, CATALOG[:1])
        self.assertEqual(source["page"], 2)

    def test_does_not_default_when_catalog_has_many_items(self):
        self.assertEqual(resolve_card_sources({}, CATALOG), [])

    def test_multiple_source_ids(self):
        sources = resolve_card_sources(
            {
                "source_ids": [
                    "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "dddddddd-dddd-dddd-dddd-dddddddddddd",
                    "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
                    "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                ]
            },
            CATALOG,
        )
        self.assertEqual(
            [item["kind"] for item in sources],
            ["page", "video", "pdf"],
        )
        self.assertEqual(sources[0]["id"], "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        self.assertEqual(sources[1]["material_id"], "dddddddd-dddd-dddd-dddd-dddddddddddd")
        self.assertNotIn("page", sources[1])

    def test_merges_legacy_source_page_id_into_source_ids(self):
        sources = resolve_card_sources(
            {
                "source_ids": ["dddddddd-dddd-dddd-dddd-dddddddddddd"],
                "source_page_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            },
            CATALOG,
        )
        self.assertEqual([item["kind"] for item in sources], ["video", "page"])

    def test_attach_strips_source_ids_and_fills_explanation(self):
        cards = attach_card_sources(
            [
                {
                    "prompt": "Subtract",
                    "source_page_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "source_ids": ["dddddddd-dddd-dddd-dddd-dddddddddddd"],
                }
            ],
            CATALOG,
        )
        self.assertNotIn("source_page_id", cards[0])
        self.assertNotIn("source_ids", cards[0])
        self.assertEqual(cards[0]["source"]["page"], 2)
        self.assertEqual(
            [item["kind"] for item in cards[0]["sources"]],
            ["video", "page"],
        )
        self.assertEqual(cards[0]["explanation"], FALLBACK_EXPLANATION)
        self.assertEqual(cards[0]["difficulty"], "easy")

    def test_attach_normalizes_intermediate_difficulty(self):
        cards = attach_card_metadata(
            [{"prompt": "Why?", "difficulty": "medium"}],
            CATALOG[:1],
        )
        self.assertEqual(cards[0]["difficulty"], "intermediate")
        self.assertEqual(cards[0]["sources"][0]["kind"], "page")

    def test_catalog_prompt_includes_kinds_and_ids_not_urls(self):
        text = format_content_catalog_for_prompt(CATALOG)
        self.assertIn("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", text)
        self.assertIn("kind=video", text)
        self.assertIn("kind=pdf", text)
        self.assertNotIn("http", text)
        self.assertNotIn("/dashboard", text)
        self.assertEqual(text, format_page_catalog_for_prompt(CATALOG))

    def test_normalize_stored_card_lifts_legacy_source(self):
        card = normalize_stored_card(
            {
                "prompt": "Add",
                "difficulty": "hard",
                "source": {
                    "material_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "page": 3,
                    "title": "Adding fractions",
                },
            }
        )
        self.assertEqual(card["difficulty"], "hard")
        self.assertEqual(len(card["sources"]), 1)
        self.assertEqual(card["sources"][0]["kind"], "page")
        self.assertEqual(card["sources"][0]["page"], 3)

    def test_normalize_difficulty_aliases(self):
        self.assertEqual(normalize_difficulty("intermediate"), "intermediate")
        self.assertEqual(normalize_difficulty("MEDIUM"), "intermediate")
        self.assertEqual(normalize_difficulty("nope"), "easy")
        self.assertEqual(normalize_difficulty("", default="hard"), "hard")


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


from studycoach.services.bank_generator import (
    card_to_item_fields,
    filter_catalog,
    resolve_sources_from_ids,
)


class CoachBankGeneratorTests(SimpleTestCase):
    def test_card_to_item_fields(self):
        fields = card_to_item_fields(
            {
                "question_type": "multiple_choice",
                "prompt": "Pick one",
                "options": ["A", "B"],
                "answer": "A",
                "hints": ["Look again."],
                "explanation": "A is right.",
                "difficulty": "intermediate",
                "sources": [{"kind": "page", "id": "1", "material_id": "2", "page": 1}],
            }
        )
        self.assertEqual(fields["question_type"], "multiple_choice")
        self.assertEqual(fields["difficulty"], "intermediate")
        self.assertEqual(fields["options"], ["A", "B"])

    def test_filter_catalog_by_ids(self):
        catalog = [
            {"id": "a", "kind": "page"},
            {"id": "b", "kind": "video"},
        ]
        self.assertEqual(filter_catalog(catalog, ["b"]), [{"id": "b", "kind": "video"}])
        self.assertEqual(filter_catalog(catalog, None), catalog)

    def test_resolve_sources_from_ids(self):
        catalog = [
            {
                "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "kind": "page",
                "material_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "page": 2,
                "title": "Fractions",
            }
        ]
        sources = resolve_sources_from_ids(
            ["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "missing"],
            catalog,
        )
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["kind"], "page")
        self.assertEqual(sources[0]["page"], 2)
