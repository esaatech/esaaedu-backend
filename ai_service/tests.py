import json

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


class TutorXAssignmentGradeSchemaTests(SimpleTestCase):
    def test_grade_schema_fields(self):
        from ai_service.schemas_tutorx_grade import TutorXQuestionGradeOut

        grade = TutorXQuestionGradeOut(
            points_earned=3.5,
            feedback="  You explained the main idea.  ",
            correct_answer=" Plants use light to make food. ",
            confidence=0.9,
        )
        self.assertEqual(grade.points_earned, 3.5)
        self.assertEqual(grade.feedback, "You explained the main idea.")
        self.assertEqual(grade.correct_answer, "Plants use light to make food.")


class TutorXAssignmentGradeRunnerTests(SimpleTestCase):
    @patch(
        "ai_service.runners.question_grade_base.get_default_prompt_config",
        return_value=None,
    )
    @patch("error_alerts.notify_ai_failure")
    def test_missing_default_prompt_alerts_slack(self, mock_notify, _mock_prompt):
        from ai_service.runners.tutorx_assignment_grade import grade_tutorx_questions_batch

        result = grade_tutorx_questions_batch(
            [
                {
                    "question_id": "q1",
                    "question_text": "Explain photosynthesis.",
                    "question_type": "essay",
                    "student_answer": "Plants make food.",
                    "points_possible": 5,
                }
            ]
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "ai_not_configured")
        self.assertIn("setup_tutorx_assignment_grade", result["error"])
        mock_notify.assert_called_once()
        self.assertEqual(mock_notify.call_args.kwargs["error_code"], "ai_not_configured")


class TeacherAndAssessmentGradeRunnerTests(SimpleTestCase):
    @patch(
        "ai_service.runners.question_grade_base.get_default_prompt_config",
        return_value=None,
    )
    @patch("error_alerts.notify_ai_failure")
    def test_teacher_missing_default_alerts_slack(self, mock_notify, _mock_prompt):
        from ai_service.runners.teacher_assignment_grade import (
            grade_teacher_assignment_questions_batch,
        )

        result = grade_teacher_assignment_questions_batch(
            [
                {
                    "question_id": "q1",
                    "question_text": "Explain photosynthesis.",
                    "question_type": "essay",
                    "student_answer": "Plants make food.",
                    "points_possible": 5,
                }
            ]
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "ai_not_configured")
        self.assertIn("setup_teacher_assignment_grade", result["error"])
        mock_notify.assert_called_once()

    @patch(
        "ai_service.runners.question_grade_base.get_default_prompt_config",
        return_value=None,
    )
    @patch("error_alerts.notify_ai_failure")
    def test_assessment_missing_default_alerts_slack(self, mock_notify, _mock_prompt):
        from ai_service.runners.assessment_grade import grade_assessment_questions_batch

        result = grade_assessment_questions_batch(
            [
                {
                    "question_id": "q1",
                    "question_text": "Explain photosynthesis.",
                    "question_type": "essay",
                    "student_answer": "Plants make food.",
                    "points_possible": 5,
                }
            ]
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "ai_not_configured")
        self.assertIn("setup_assessment_grade", result["error"])
        mock_notify.assert_called_once()


class DocumentPartsTests(SimpleTestCase):
    def test_normalize_storage_url_to_gs_for_gemini(self):
        from ai_service.runners.document_parts import normalize_storage_url

        self.assertEqual(
            normalize_storage_url(
                "https://storage.googleapis.com/my-bucket/path/file.pdf?X-Goog-Signature=abc",
                provider="gemini",
            ),
            "gs://my-bucket/path/file.pdf",
        )
        self.assertEqual(
            normalize_storage_url("gs://my-bucket/path/file.pdf", provider="gemini"),
            "gs://my-bucket/path/file.pdf",
        )
        self.assertEqual(
            normalize_storage_url(
                "https://storage.googleapis.com/sbtyacademy/documents/id-The%20story%20keepers.pdf",
                provider="gemini",
            ),
            "gs://sbtyacademy/documents/id-The story keepers.pdf",
        )

    def test_normalize_storage_url_https_for_deepseek(self):
        from ai_service.runners.document_parts import normalize_storage_url

        self.assertEqual(
            normalize_storage_url(
                "gs://my-bucket/path/file.pdf",
                provider="deepseek",
            ),
            "https://storage.googleapis.com/my-bucket/path/file.pdf",
        )
        self.assertEqual(
            normalize_storage_url(
                "https://storage.googleapis.com/my-bucket/path/file.pdf?X-Goog-Signature=abc",
                provider="deepseek",
            ),
            "https://storage.googleapis.com/my-bucket/path/file.pdf",
        )

    @patch(
        "ai_service.runners.document_parts._download_bytes",
        return_value=b"%PDF",
    )
    @patch(
        "ai_service.runners.document_parts._extract_pdf_text",
        return_value="Once upon a time there were two stories.",
    )
    def test_deepseek_prompt_inlines_extracted_pdf_text(self, _extract, _download):
        from ai_service.runners.document_parts import user_prompt_with_documents

        prompt = user_prompt_with_documents(
            "Generate a quiz.",
            [
                {
                    "uri": "gs://bucket/lesson.pdf",
                    "mime_type": "application/pdf",
                    "title": "Two Stories",
                }
            ],
            provider="deepseek",
        )
        self.assertIsInstance(prompt, str)
        self.assertIn("Once upon a time", prompt)
        self.assertIn("Two Stories", prompt)


class QuizAssignmentGenerateConfigTests(SimpleTestCase):
    @patch(
        "ai_service.runners.quiz_generate.get_default_prompt_config",
        return_value=None,
    )
    @patch("error_alerts.notify_ai_failure")
    def test_quiz_missing_default_alerts_slack(self, mock_notify, _mock_prompt):
        from ai_service.runners.quiz_generate import generate_quiz

        result = generate_quiz(
            lesson_title="Python Basics",
            content="Variables store values.",
            total_questions=2,
            multiple_choice_count=1,
            true_false_count=1,
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "ai_not_configured")
        self.assertIn("setup_quiz_generate", result["error"])
        mock_notify.assert_called_once()

    @patch(
        "ai_service.runners.assignment_generate.get_default_prompt_config",
        return_value=None,
    )
    @patch("error_alerts.notify_ai_failure")
    def test_assignment_missing_default_alerts_slack(self, mock_notify, _mock_prompt):
        from ai_service.runners.assignment_generate import generate_assignment

        result = generate_assignment(
            lesson_title="Python Basics",
            content="Variables store values.",
            total_questions=2,
            essay_count=1,
            fill_blank_count=1,
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "ai_not_configured")
        self.assertIn("setup_assignment_generate", result["error"])
        mock_notify.assert_called_once()

    def test_quiz_schema_normalizes_options(self):
        from ai_service.schemas_quiz_generate import QuizGenerateOut, QuizQuestionOut
        from ai_service.runners.quiz_generate import _normalize_quiz

        quiz = QuizGenerateOut(
            title="Quiz",
            description="Desc",
            questions=[
                QuizQuestionOut(
                    question_text="What is 2+2?",
                    type="multiple_choice",
                    points=1,
                    options=["3", "4", "5"],
                    correct_answer="4",
                    explanation="Add them.",
                ),
                QuizQuestionOut(
                    question_text="Python is a language.",
                    type="true_false",
                    points=1,
                    correct_answer="True",
                    explanation="Yes.",
                ),
            ],
        )
        payload = _normalize_quiz(quiz, fallback_title="Fallback")
        self.assertEqual(len(payload["questions"]), 2)
        self.assertEqual(payload["questions"][0]["content"]["options"], ["3", "4", "5"])
        self.assertEqual(payload["questions"][0]["content"]["correct_answer"], "4")
        self.assertEqual(payload["questions"][1]["content"]["correct_answer"], "true")

    def test_assignment_requires_explanation_and_correct_answer(self):
        from ai_service.schemas_assignment_generate import AssignmentQuestionOut

        with self.assertRaises(Exception):
            AssignmentQuestionOut(
                question_text="Explain variables.",
                type="essay",
                points=5,
                content={"instructions": "Write a short answer."},
                explanation="",
            )
        from ai_service.schemas_quiz_generate import QuizQuestionOut

        with self.assertRaises(Exception):
            QuizQuestionOut(
                question_text="What is 2+2?",
                type="multiple_choice",
                points=1,
                explanation="Add them.",
            )

    def test_normalize_accepts_choice_objects(self):
        from ai_service.schemas_quiz_generate import QuizQuestionOut
        from ai_service.runners.quiz_generate import _normalize_question

        q = QuizQuestionOut(
            question_text="Pick one",
            type="multiple_choice",
            options=[{"label": "A"}, {"text": "B"}, {"value": "C"}],
            correct_answer="B",
            explanation="B is right.",
        )
        item = _normalize_question(q)
        self.assertIsNotNone(item)
        self.assertEqual(item["content"]["options"], ["A", "B", "C"])


class StudioSystemInstructionSchemaTests(SimpleTestCase):
    def test_requires_full_prompt(self):
        from ai_service.schemas_studio import StudioSystemInstructionOut

        out = StudioSystemInstructionOut(
            system_prompt="You draft a lesson as beats for a teacher. Keep lines short.",
            summary="Kept one-breath lines.",
        )
        self.assertIn("beats", out.system_prompt)

    def test_rejects_short_prompt(self):
        from ai_service.schemas_studio import StudioSystemInstructionOut

        with self.assertRaises(Exception):
            StudioSystemInstructionOut(system_prompt="too short", summary="no")


class StudioSettingsTests(SimpleTestCase):
    def test_prompt_model_wins_over_env(self):
        from ai_service.studio_settings import settings_patch_for_prompt

        class Model:
            provider = "openai"
            model_id = "gpt-4o-mini"
            default_temperature = None

        class Prompt:
            system_prompt = "Draft beats."
            temperature = 0.4
            ai_model = Model()

        patch = settings_patch_for_prompt(Prompt())
        self.assertEqual(patch["provider"], "openai")
        self.assertEqual(patch["model_id"], "gpt-4o-mini")
        self.assertEqual(patch["temperature"], 0.4)
        self.assertEqual(patch["system_prompt"], "Draft beats.")

    def test_push_skips_when_studio_env_missing(self):
        from unittest.mock import patch

        from ai_service.studio_settings import push_studio_settings

        with patch("ai_service.studio_settings.studio_base_url", return_value=""):
            result = push_studio_settings()
        self.assertTrue(result.skipped)
        self.assertTrue(result.ok)

    def test_rewrite_requires_a_change_request(self):
        from ai_service.runners.studio_system_instruction import (
            rewrite_studio_system_instruction,
        )

        result = rewrite_studio_system_instruction(
            target_service="studio_script_drafter",
            current_prompt="You draft a lesson as beats for a teacher.",
            change_request="",
        )
        self.assertFalse(result["success"])
        self.assertIn("change", result["error"].lower())


class StudioVisualPlaygroundTests(SimpleTestCase):
    def test_spoken_line_and_on_screen_are_required(self):
        from ai_service.runners.studio_visual import generate_studio_visual

        missing_line = generate_studio_visual(spoken_line="", on_screen="A person outline.")
        missing_screen = generate_studio_visual(spoken_line="Welcome.", on_screen="")
        self.assertFalse(missing_line["success"])
        self.assertFalse(missing_screen["success"])

    def test_posts_the_chosen_prompt_to_studio(self):
        from unittest.mock import MagicMock, patch

        from ai_service.runners.studio_visual import generate_studio_visual

        class Model:
            provider = "deepseek"
            model_id = "deepseek-chat"
            default_temperature = None

        class Service:
            slug = "studio_visual_generator"

        class Prompt:
            slug = "try-person"
            system_prompt = "Choose a person outline when the line is a greeting."
            temperature = 0.2
            ai_model = Model()
            service = Service()

        posted = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(
                    {
                        "component": "shape-picture",
                        "settings": {"subject": "person", "title": "English Adventure", "labels": ["Welcome"]},
                        "html": "<html><body>person</body></html>",
                        "duration": None,
                    }
                ).encode("utf-8")

        def fake_urlopen(request, timeout=0):
            posted["url"] = request.full_url
            posted["body"] = json.loads(request.data.decode("utf-8"))
            posted["timeout"] = timeout
            return FakeResponse()

        with patch("ai_service.runners.studio_visual.studio_base_url", return_value="http://127.0.0.1:8001"):
            with patch("ai_service.runners.studio_visual.urllib.request.urlopen", fake_urlopen):
                result = generate_studio_visual(
                    spoken_line="Welcome, explorers, to our English Adventure where words come alive!",
                    on_screen="A person outline titled English Adventure, labeled Welcome and Explorers.",
                    generate_audio="",
                    prompt_config=Prompt(),
                )

        self.assertTrue(result["success"])
        self.assertEqual(result["result"]["component"], "shape-picture")
        self.assertIn("person", result["result"]["html"])
        self.assertFalse(posted["body"]["generate_audio"])
        self.assertEqual(posted["body"]["visual_generator"]["model_id"], "deepseek-chat")
        self.assertIn("person outline", posted["body"]["visual_generator"]["system_prompt"])
        self.assertEqual(posted["url"], "http://127.0.0.1:8001/v1/visuals")
        self.assertEqual(posted["timeout"], 180)
        self.assertEqual(posted["body"]["kind"], "concept")

    def test_admin_runner_forwards_kind(self):
        from unittest.mock import patch

        from ai_service.admin import _studio_visual_runner

        class Service:
            slug = "studio_visual_generator"

        class Prompt:
            slug = "try-title"
            system_prompt = "Use title-card for intro."
            temperature = 0.2
            ai_model = None
            service = Service()

        posted = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(
                    {
                        "component": "kinetic-text",
                        "settings": {"sentence": "I walk to school", "motion": "highlight"},
                        "html": "<html></html>",
                    }
                ).encode("utf-8")

        def fake_urlopen(request, timeout=0):
            posted["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        with patch("ai_service.runners.studio_visual.studio_base_url", return_value="http://127.0.0.1:8001"):
            with patch("ai_service.runners.studio_visual.urllib.request.urlopen", fake_urlopen):
                result = _studio_visual_runner(
                    spoken_line="I walk to school.",
                    on_screen="I walk to school.",
                    kind="wording",
                    prompt_config=Prompt(),
                )

        self.assertTrue(result["success"])
        self.assertEqual(posted["body"]["kind"], "wording")
        self.assertEqual(result["result"]["kind"], "wording")

    def test_playground_sends_the_chosen_kind(self):
        from unittest.mock import patch

        from ai_service.runners.studio_visual import generate_studio_visual

        class Service:
            slug = "studio_visual_generator"

        class Prompt:
            slug = "try-title"
            system_prompt = "Use title-card for intro."
            temperature = 0.2
            ai_model = None
            service = Service()

        posted = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(
                    {
                        "component": "title-card",
                        "settings": {"title": "English", "subtitle": "", "emblem": "book"},
                        "html": "<html><body>English</body></html>",
                    }
                ).encode("utf-8")

        def fake_urlopen(request, timeout=0):
            posted["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        with patch("ai_service.runners.studio_visual.studio_base_url", return_value="http://127.0.0.1:8001"):
            with patch("ai_service.runners.studio_visual.urllib.request.urlopen", fake_urlopen):
                result = generate_studio_visual(
                    spoken_line="Welcome to English.",
                    on_screen="Title English with a book.",
                    kind="intro",
                    prompt_config=Prompt(),
                )

        self.assertTrue(result["success"])
        self.assertEqual(posted["body"]["kind"], "intro")
        self.assertEqual(result["result"]["component"], "title-card")

    def test_rejects_a_prompt_from_another_service(self):
        from ai_service.runners.studio_visual import generate_studio_visual

        class Service:
            slug = "studio_script_drafter"

        class Prompt:
            slug = "default"
            system_prompt = "Draft beats."
            temperature = 0.4
            ai_model = None
            service = Service()

        result = generate_studio_visual(
            spoken_line="Welcome.",
            on_screen="A person outline labeled Welcome.",
            prompt_config=Prompt(),
        )
        self.assertFalse(result["success"])
        self.assertIn("Visual Generator", result["error"])

