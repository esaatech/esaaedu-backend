from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.models import Lesson

from .models import StudySession
from .serializers import (
    StudySessionAnswerSerializer,
    StudySessionCreateSerializer,
    StudySessionExtendSerializer,
    StudySessionListSerializer,
    StudySessionSerializer,
)
from .services.access import user_can_study_lesson
from .services.deck_generator import (
    MAX_CARD_COUNT,
    clamp_card_count,
    generate_deck_for_lesson,
)
from .services.static_generator import (
    card_avoid_label,
    check_card_answer,
    dedupe_cards,
    default_progress,
)

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
    """POST an answer for the current card; updates progress."""

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
        card = next((c for c in session.cards if str(c.get("id")) == card_id), None)
        if not card:
            return Response(
                {"error": "Card not found in this session"},
                status=status.HTTP_404_NOT_FOUND,
            )

        progress = dict(session.progress or default_progress())
        answers = dict(progress.get("answers") or {})

        # Idempotent: don't double-count if this card was already graded.
        if card_id in answers:
            existing = answers[card_id] or {}
            return Response(
                {
                    "correct": bool(existing.get("correct")),
                    "answer": card.get("answer"),
                    "explanation": card.get("explanation"),
                    "session": StudySessionSerializer(session).data,
                }
            )

        response_text = serializer.validated_data["response"]
        correct = check_card_answer(card, response_text)
        answers[card_id] = {
            "response": response_text,
            "correct": correct,
            "used_hint_count": serializer.validated_data.get("used_hint_count", 0),
            "flipped": serializer.validated_data.get("flipped", False),
            "skipped": not str(response_text or "").strip(),
        }
        progress["answers"] = answers
        if correct:
            progress["correct_count"] = int(progress.get("correct_count") or 0) + 1
            progress["streak"] = int(progress.get("streak") or 0) + 1
        else:
            progress["incorrect_count"] = int(progress.get("incorrect_count") or 0) + 1
            progress["streak"] = 0

        # Advance index if this was the current card
        current_index = int(progress.get("current_index") or 0)
        if (
            0 <= current_index < len(session.cards)
            and str(session.cards[current_index].get("id")) == card_id
        ):
            progress["current_index"] = min(current_index + 1, len(session.cards))

        if progress["current_index"] >= len(session.cards):
            session.status = "completed"

        session.progress = progress
        session.save(update_fields=["progress", "status", "updated_at"])

        return Response(
            {
                "correct": correct,
                "answer": card.get("answer"),
                "explanation": card.get("explanation"),
                "session": StudySessionSerializer(session).data,
            }
        )
