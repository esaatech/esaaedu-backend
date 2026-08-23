from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.models import Lesson

from .models import CoachBank, CoachItem, CoachLessonMemory, StudySession
from .serializers import (
    CoachBankGenerateSerializer,
    CoachBankSerializer,
    CoachItemSerializer,
    CoachItemWriteSerializer,
    CoachLessonMemorySerializer,
    StudySessionAnswerSerializer,
    StudySessionCreateSerializer,
    StudySessionExtendSerializer,
    StudySessionListSerializer,
    StudySessionSerializer,
)
from .services.access import user_can_manage_lesson_bank, user_can_study_lesson
from .services.bank_generator import (
    MAX_BANK_ITEMS,
    draw_cards_from_bank,
    generate_into_bank,
    resolve_sources_from_ids,
)
from .services.card_metadata import build_content_catalog
from .services.deck_generator import (
    MAX_CARD_COUNT,
    clamp_card_count,
    generate_deck_for_lesson,
)
from .services.lesson_memory import (
    clear_study_gate,
    get_memory,
    study_gate_blocks,
)
from .services.session_grade import grade_and_coach_session
from .services.static_generator import (
    card_avoid_label,
    default_progress,
    dedupe_cards,
)
from .services.grading import StudyCoachGradeError

class StudySessionListCreateView(APIView):
    """
    GET: list recent Study Coach sessions for the current student.
    POST: create a session and generate an AI quiz deck for the lesson.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, "student_profile"):
            return Response(
                {"error": "Only students can use Study Coach"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            limit = int(request.query_params.get("limit", 10))
        except (TypeError, ValueError):
            limit = 10
        try:
            offset = int(request.query_params.get("offset", 0))
        except (TypeError, ValueError):
            offset = 0
        limit = max(1, min(limit, 50))
        offset = max(0, offset)

        qs = StudySession.objects.filter(student=request.user).select_related(
            "lesson", "lesson__course"
        )
        total = qs.count()
        page = list(qs[offset : offset + limit])
        return Response(
            {
                "results": StudySessionListSerializer(page, many=True).data,
                "count": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(page) < total,
            }
        )

    def post(self, request):
        if not hasattr(request.user, "student_profile"):
            return Response(
                {"error": "Only students can use Study Coach"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = StudySessionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        lesson = get_object_or_404(Lesson, id=serializer.validated_data["lesson_id"])
        if not user_can_study_lesson(request.user, lesson):
            return Response(
                {"error": "You must be enrolled in this course to study this lesson"},
                status=status.HTTP_403_FORBIDDEN,
            )

        difficulty_mode = serializer.validated_data["difficulty_mode"]
        card_count = clamp_card_count(serializer.validated_data.get("card_count"))
        memory = get_memory(request.user, lesson)
        if difficulty_mode == "auto" and study_gate_blocks(memory):
            return Response(
                {
                    "error": "Read the lesson pages first, then tap I’ve reread the topic.",
                    "error_code": "study_required",
                    "memory": CoachLessonMemorySerializer(memory).data,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        next_mix = None
        if difficulty_mode == "auto" and memory is not None:
            next_mix = memory.next_mix or None

        bank_cards = draw_cards_from_bank(
            lesson,
            difficulty_mode=difficulty_mode,
            card_count=card_count,
            next_mix=next_mix,
        )
        if bank_cards is not None:
            if not bank_cards:
                return Response(
                    {
                        "error": "This lesson bank has no matching practice questions for that mix.",
                        "error_code": "bank_empty_filter",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            session = StudySession.objects.create(
                student=request.user,
                lesson=lesson,
                difficulty_mode=difficulty_mode,
                grounding_mode="bank",
                status="active",
                cards=bank_cards,
                progress=default_progress(),
            )
            return Response(
                StudySessionSerializer(session).data,
                status=status.HTTP_201_CREATED,
            )

        deck = generate_deck_for_lesson(
            lesson=lesson,
            difficulty_mode=difficulty_mode,
            card_count=card_count,
        )
        if not deck.get("success"):
            return Response(
                {
                    "error": deck.get("error"),
                    "error_code": deck.get("error_code") or "generation_failed",
                },
                status=deck.get("status_code") or status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        grounding_mode = deck.get("grounding_mode") or "title"
        if grounding_mode not in ("grounded", "title"):
            grounding_mode = "title"

        session = StudySession.objects.create(
            student=request.user,
            lesson=lesson,
            difficulty_mode=difficulty_mode,
            grounding_mode=grounding_mode,
            status="active",
            cards=deck["cards"],
            progress=default_progress(),
        )
        return Response(
            StudySessionSerializer(session).data,
            status=status.HTTP_201_CREATED,
        )


class StudySessionDetailView(APIView):
    """GET one Study Coach session owned by the current student."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, session_id):
        session = get_object_or_404(
            StudySession.objects.select_related("lesson", "lesson__course"),
            id=session_id,
            student=request.user,
        )
        return Response(StudySessionSerializer(session).data)


class StudySessionExtendView(APIView):
    """POST: append more AI cards to an existing session (same session, max 20)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        if not hasattr(request.user, "student_profile"):
            return Response(
                {"error": "Only students can use Study Coach"},
                status=status.HTTP_403_FORBIDDEN,
            )

        session = get_object_or_404(
            StudySession.objects.select_related("lesson", "lesson__course"),
            id=session_id,
            student=request.user,
        )
        serializer = StudySessionExtendSerializer(data=request.data or {})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        existing = list(session.cards or [])
        remaining = MAX_CARD_COUNT - len(existing)
        if remaining <= 0:
            return Response(
                {
                    "error": f"This quiz already has the maximum of {MAX_CARD_COUNT} cards.",
                    "error_code": "max_cards_reached",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        requested = int(serializer.validated_data.get("card_count") or 6)
        card_count = max(1, min(requested, remaining, MAX_CARD_COUNT))

        avoid_prompts = [
            label
            for label in (card_avoid_label(c) for c in existing)
            if label
        ]
        memory = get_memory(request.user, session.lesson)
        next_mix = (
            memory.next_mix
            if session.difficulty_mode == "auto" and memory is not None
            else None
        )
        bank_cards = draw_cards_from_bank(
            session.lesson,
            difficulty_mode=session.difficulty_mode,
            card_count=card_count,
            exclude_prompts=avoid_prompts,
            next_mix=next_mix,
        )
        if bank_cards is not None:
            if not bank_cards:
                return Response(
                    {
                        "error": "No more practice questions in this lesson bank.",
                        "error_code": "bank_exhausted",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            new_cards = bank_cards
        else:
            deck = generate_deck_for_lesson(
                lesson=session.lesson,
                difficulty_mode=session.difficulty_mode,
                card_count=card_count,
                avoid_prompts=avoid_prompts,
            )
            if not deck.get("success"):
                return Response(
                    {
                        "error": deck.get("error"),
                        "error_code": deck.get("error_code") or "generation_failed",
                    },
                    status=deck.get("status_code") or status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            new_cards = dedupe_cards(list(deck.get("cards") or []), existing=existing)
            if not new_cards:
                return Response(
                    {
                        "error": "We couldn't generate more cards right now. Please try again.",
                        "error_code": "generation_failed",
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        # Keep only what fits under the session cap.
        room = MAX_CARD_COUNT - len(existing)
        appended = new_cards[:room]
        resume_index = len(existing)
        session.cards = existing + appended

        progress = dict(session.progress or default_progress())
        # Continue from the first newly added card.
        progress["current_index"] = resume_index
        session.progress = progress
        session.status = "active"
        session.save(update_fields=["cards", "progress", "status", "updated_at"])

        return Response(
            {
                "added": len(appended),
                "resume_index": resume_index,
                "session": StudySessionSerializer(session).data,
            },
            status=status.HTTP_200_OK,
        )


class StudySessionAnswerView(APIView):
    """POST: save a response for a card. Does not grade. Check is client-side reveal."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(
            StudySession.objects.select_related("lesson"),
            id=session_id,
            student=request.user,
        )
        serializer = StudySessionAnswerSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        card_id = str(serializer.validated_data["card_id"])
        cards = list(session.cards or [])
        card = next((c for c in cards if str(c.get("id")) == card_id), None)
        if not card:
            return Response(
                {"error": "Card not found in this session"},
                status=status.HTTP_404_NOT_FOUND,
            )

        progress = dict(session.progress or default_progress())
        answers = dict(progress.get("answers") or {})
        existing = dict(answers.get(card_id) or {})
        if progress.get("graded") or existing.get("graded"):
            return Response(
                {
                    "correct": existing.get("correct"),
                    "answer": card.get("answer"),
                    "explanation": card.get("explanation"),
                    "session": StudySessionSerializer(session).data,
                }
            )

        response_text = serializer.validated_data["response"]
        answers[card_id] = {
            "response": response_text,
            "used_hint_count": serializer.validated_data.get("used_hint_count", 0),
            "flipped": serializer.validated_data.get("flipped", False),
            "skipped": not str(response_text or "").strip(),
            "graded": False,
        }
        progress["answers"] = answers

        card_index = next(
            (i for i, c in enumerate(cards) if str(c.get("id")) == card_id),
            int(progress.get("current_index") or 0),
        )
        if serializer.validated_data.get("advance"):
            progress["current_index"] = min(card_index + 1, len(cards))
        else:
            progress["current_index"] = card_index

        session.progress = progress
        session.save(update_fields=["progress", "updated_at"])

        return Response(
            {
                "correct": None,
                "answer": card.get("answer"),
                "explanation": card.get("explanation"),
                "session": StudySessionSerializer(session).data,
            }
        )


class StudySessionGradeView(APIView):
    """POST: grade saved answers (essays via AI), then coach feedback in the same request."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(
            StudySession.objects.select_related("lesson", "lesson__course"),
            id=session_id,
            student=request.user,
        )
        try:
            result = grade_and_coach_session(session)
        except StudyCoachGradeError as exc:
            return Response(
                {
                    "error": str(exc),
                    "error_code": exc.error_code,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        session = result["session"]
        return Response(
            {
                "session": StudySessionSerializer(session).data,
                "feedback": result["feedback"],
                "memory": CoachLessonMemorySerializer(result["memory"]).data,
            }
        )


class CoachMemoryListView(APIView):
    """GET recent Auto memories for the current student (study gate + last feedback)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, "student_profile"):
            return Response(
                {"error": "Only students can use Study Coach"},
                status=status.HTTP_403_FORBIDDEN,
            )
        rows = list(
            CoachLessonMemory.objects.filter(student=request.user)
            .select_related("lesson", "lesson__course", "last_session")[:50]
        )
        return Response(
            {
                "results": CoachLessonMemorySerializer(rows, many=True).data,
                "count": len(rows),
            }
        )


class CoachMemoryRereadView(APIView):
    """POST: student confirms they reread the assigned pages; unlocks Auto retake."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, lesson_id):
        if not hasattr(request.user, "student_profile"):
            return Response(
                {"error": "Only students can use Study Coach"},
                status=status.HTTP_403_FORBIDDEN,
            )
        lesson = get_object_or_404(Lesson, id=lesson_id)
        memory = get_memory(request.user, lesson)
        if not memory:
            return Response(
                {"error": "No Study Coach memory for this lesson.", "error_code": "not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        memory = clear_study_gate(memory)
        return Response(CoachLessonMemorySerializer(memory).data)


def _teacher_lesson(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    if not user_can_manage_lesson_bank(request.user, lesson):
        return None, Response(
            {"error": "Only course teachers can manage this practice bank"},
            status=status.HTTP_403_FORBIDDEN,
        )
    return lesson, None


def _serialize_bank(bank):
    bank.item_count = bank.items.count()
    return CoachBankSerializer(bank).data


class LessonCoachBankView(APIView):
    """GET: get-or-create the practice bank for a lesson. DELETE: remove it."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, lesson_id):
        lesson, error = _teacher_lesson(request, lesson_id)
        if error:
            return error
        bank, _created = CoachBank.objects.get_or_create(lesson=lesson)
        return Response(_serialize_bank(bank))

    def delete(self, request, lesson_id):
        lesson, error = _teacher_lesson(request, lesson_id)
        if error:
            return error
        CoachBank.objects.filter(lesson=lesson).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LessonCoachCatalogView(APIView):
    """Lesson pages / videos / PDFs the teacher can tag on questions."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, lesson_id):
        lesson, error = _teacher_lesson(request, lesson_id)
        if error:
            return error
        catalog = build_content_catalog(lesson)
        return Response({"results": catalog, "count": len(catalog)})


class LessonCoachGenerateView(APIView):
    """Append AI practice questions to the lesson bank."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, lesson_id):
        lesson, error = _teacher_lesson(request, lesson_id)
        if error:
            return error
        serializer = CoachBankGenerateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        bank, _created = CoachBank.objects.get_or_create(lesson=lesson)
        result = generate_into_bank(
            bank,
            difficulty_mode=serializer.validated_data["difficulty_mode"],
            card_count=serializer.validated_data.get("card_count") or 10,
            source_ids=serializer.validated_data.get("source_ids") or [],
        )
        if not result.get("success"):
            return Response(
                {
                    "error": result.get("error"),
                    "error_code": result.get("error_code") or "generation_failed",
                    "bank": _serialize_bank(bank),
                },
                status=result.get("status_code") or status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {
                "added": result.get("added") or 0,
                "bank": _serialize_bank(bank),
            },
            status=status.HTTP_201_CREATED,
        )


class LessonCoachItemListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, lesson_id):
        lesson, error = _teacher_lesson(request, lesson_id)
        if error:
            return error
        bank, _created = CoachBank.objects.get_or_create(lesson=lesson)
        if bank.items.count() >= MAX_BANK_ITEMS:
            return Response(
                {"error": "This lesson already has 100 practice questions."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = CoachItemWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        catalog = build_content_catalog(lesson)
        source_ids = serializer.validated_data.pop("source_ids", None)
        payload = dict(serializer.validated_data)
        if source_ids is not None:
            payload["sources"] = resolve_sources_from_ids(source_ids, catalog)
        elif payload.get("sources"):
            payload["sources"] = resolve_sources_from_ids(
                [str(s.get("id") or "") for s in payload["sources"] if isinstance(s, dict)],
                catalog,
            )
        last = bank.items.order_by("-order").first()
        payload["order"] = (last.order + 1) if last else 1
        if not payload.get("hints"):
            payload["hints"] = ["Think about what the lesson covers."]
        item = CoachItem.objects.create(bank=bank, **payload)
        bank.save(update_fields=["updated_at"])
        return Response(CoachItemSerializer(item).data, status=status.HTTP_201_CREATED)


class CoachItemDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _item_for_teacher(self, request, item_id):
        item = get_object_or_404(CoachItem.objects.select_related("bank__lesson__course"), id=item_id)
        if not user_can_manage_lesson_bank(request.user, item.bank.lesson):
            return None, Response(
                {"error": "Only course teachers can manage this practice bank"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return item, None

    def patch(self, request, item_id):
        item, error = self._item_for_teacher(request, item_id)
        if error:
            return error
        serializer = CoachItemWriteSerializer(item, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        catalog = build_content_catalog(item.bank.lesson)
        source_ids = serializer.validated_data.pop("source_ids", None)
        for key, value in serializer.validated_data.items():
            setattr(item, key, value)
        if source_ids is not None:
            item.sources = resolve_sources_from_ids(source_ids, catalog)
        item.save()
        item.bank.save(update_fields=["updated_at"])
        return Response(CoachItemSerializer(item).data)

    def delete(self, request, item_id):
        item, error = self._item_for_teacher(request, item_id)
        if error:
            return error
        bank = item.bank
        item.delete()
        bank.save(update_fields=["updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
