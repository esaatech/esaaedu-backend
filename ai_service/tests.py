from django.test import SimpleTestCase, override_settings

from ai_service.config import resolve_generation_settings


class ResolveGenerationSettingsTests(SimpleTestCase):
    @override_settings(GEMINI_MODEL="gemini-2.5-flash")
    def test_defaults_to_gemini_from_env(self):
        settings = resolve_generation_settings()
        self.assertEqual(settings.provider, "gemini")
        self.assertTrue(settings.model_id)

    def test_explicit_openai_override(self):
        settings = resolve_generation_settings(
            provider="openai",
            model_id="gpt-4o-mini",
            temperature=0.2,
        )
        self.assertEqual(settings.provider, "openai")
        self.assertEqual(settings.model_id, "gpt-4o-mini")
        self.assertEqual(settings.temperature, 0.2)

    def test_rejects_unknown_provider(self):
        with self.assertRaises(ValueError):
            resolve_generation_settings(provider="anthropic")


from ai_service.schemas_study_coach import StudyCardOut, StudyDeckOut


class StudyCoachSchemaTests(SimpleTestCase):
    def test_mcq_requires_options_and_matching_answer(self):
        card = StudyCardOut(
            question_type="multiple_choice",
            prompt="What is 2+2?",
            options=["3", "4", "5"],
            answer="4",
            hints=["Add the numbers.", "It is an even number."],
            explanation="Add 2 and 2 to get 4.",
            difficulty="easy",
        )
        self.assertEqual(card.answer, "4")

    def test_deck_min_cards(self):
        # Empty decks are allowed by schema; product layer rejects empty cards.
        deck = StudyDeckOut(cards=[])
        self.assertEqual(deck.cards, [])

    def test_column_math_display_json_optional(self):
        card = StudyCardOut(
            question_type="short_answer",
            prompt="Add these numbers.",
            answer="77",
            hints=["Line up the ones place."],
            explanation="Add the ones, then the tens.",
            difficulty="easy",
            display_json='{"type":"column_math","operator":"+","operands":["42","35"]}',
        )
        self.assertIn("column_math", card.display_json or "")

    def test_source_ids_optional_and_intermediate_difficulty(self):
        card = StudyCardOut(
            question_type="short_answer",
            prompt="What is 4/10 simplified thinking?",
            answer="4/10",
            hints=["Keep the denominator."],
            explanation="Subtract the numerators and keep the same denominator.",
            source_ids=["11111111-1111-1111-1111-111111111111"],
            source_page_id="11111111-1111-1111-1111-111111111111",
            difficulty="intermediate",
        )
        self.assertEqual(card.difficulty, "intermediate")
        self.assertEqual(card.source_ids, ["11111111-1111-1111-1111-111111111111"])
        self.assertEqual(card.source_page_id, "11111111-1111-1111-1111-111111111111")
        self.assertIn("denominator", card.explanation or "")

    def test_explanation_required(self):
        with self.assertRaises(Exception):
            StudyCardOut(
                question_type="short_answer",
                prompt="What is 2+2?",
                answer="4",
                hints=["Add them."],
                explanation="   ",
                difficulty="easy",
            )

    def test_grade_schema_is_tiny(self):
        from ai_service.schemas_study_coach import StudyCardGradeOut

        grade = StudyCardGradeOut(correct=True, feedback="You got the core idea.")
        self.assertTrue(grade.correct)


from unittest.mock import patch

from ai_service.exceptions import AIServiceError, from_exception


class AIServiceErrorClassificationTests(SimpleTestCase):
    def test_429_message_maps_to_rate_limited(self):
        err = from_exception(Exception("Error 429: Too Many Requests / rate limit exceeded"))
        self.assertIsInstance(err, AIServiceError)
        self.assertEqual(err.error_code, "rate_limited")
        self.assertEqual(err.status_code, 429)
        self.assertTrue(err.notify_admin)

    def test_resource_exhausted_maps_to_rate_limited(self):
        err = from_exception(Exception("RESOURCE_EXHAUSTED: Quota exceeded"))
        self.assertEqual(err.error_code, "rate_limited")

    def test_status_code_attr_429(self):
        class FakeHttpError(Exception):
            status_code = 429

        err = from_exception(FakeHttpError("quota"))
        self.assertEqual(err.error_code, "rate_limited")

    def test_passthrough_existing_ai_service_error(self):
        original = AIServiceError(
            error_code="generation_failed",
            log_message="boom",
            notify_admin=False,
        )
        self.assertIs(from_exception(original), original)

    @patch("error_alerts.notify_ai_failure")
    def test_notify_and_classify_sends_slack(self, mock_notify):
        from ai_service.alerts import notify_and_classify

        ai_exc = notify_and_classify(
            Exception("429 rate limit"),
            context="test",
            endpoint="ai_service.tests",
        )
        self.assertEqual(ai_exc.error_code, "rate_limited")
        self.assertTrue(ai_exc.slack_notified)
        mock_notify.assert_called_once()
        kwargs = mock_notify.call_args.kwargs
        self.assertEqual(kwargs["error_code"], "rate_limited")
        self.assertTrue(kwargs["notify_admin"])

    @patch("ai_service.alerts.logger")
    def test_log_run_model_info(self, mock_logger):
        from ai_service.alerts import log_run_model

        log_run_model(
            service="study_coach_deck",
            provider="gemini",
            model_id="gemini-2.5-flash",
            temperature=0.4,
        )
        mock_logger.info.assert_called_once()
        args = mock_logger.info.call_args[0]
        self.assertIn("ai_service.run", args[0])
        self.assertEqual(args[1], "study_coach_deck")
        self.assertEqual(args[2], "gemini")
        self.assertEqual(args[3], "gemini-2.5-flash")


class StudyCoachDeckPromptTests(SimpleTestCase):
    def test_avoid_list_includes_up_to_bank_cap(self):
        from ai_service.runners.study_coach_deck import (
            MAX_AVOID_PROMPTS,
            _build_user_prompt,
        )

        self.assertEqual(MAX_AVOID_PROMPTS, 100)
        labels = [f"Question {i} about current" for i in range(100)]
        prompt = _build_user_prompt(
            title="Electricity",
            grounding="",
            mode="auto",
            count=10,
            avoid_prompts=labels,
        )
        self.assertIn("Question 0 about current", prompt)
        self.assertIn("Question 99 about current", prompt)
        self.assertNotIn("Question 100 about current", prompt)


class StudyCoachFeedbackSchemaTests(SimpleTestCase):
    def test_feedback_schema_accepts_study_action(self):
        from ai_service.schemas_study_coach import StudyCoachFeedbackOut

        out = StudyCoachFeedbackOut(
            headline="Study subtraction",
            message="Open those pages, then try easy subtraction again.",
            action="study_then_retake",
            next_mix={"easy": 6, "intermediate": 0, "hard": 0, "order": "easy_first", "source_ids": ["abc"]},
            study_source_ids=["abc"],
        )
        self.assertEqual(out.action, "study_then_retake")
        self.assertEqual(out.next_mix.source_ids, ["abc"])


class RunAgentSyncLoopTests(SimpleTestCase):
    def test_two_sequential_runs_share_one_loop(self):
        from ai_service.runners.run_helpers import run_agent_sync

        class FakeAgent:
            async def run(self, prompt: str):
                import asyncio

                await asyncio.sleep(0)
                return type("Result", (), {"output": prompt})()

        agent = FakeAgent()
        first = run_agent_sync(agent, "one", timeout_seconds=5)
        second = run_agent_sync(agent, "two", timeout_seconds=5)
        self.assertEqual(first.output, "one")
        self.assertEqual(second.output, "two")

