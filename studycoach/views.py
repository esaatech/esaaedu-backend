from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.models import Lesson

from .models import StudySession
from .serializers import (
    StudySessionAnswerSerializer,
    StudySessionCreateSerializer,
    StudySessionSerializer,
)
from .services.access import user_can_study_lesson
from .services.static_generator import (
    check_card_answer,
    default_progress,
    generate_static_cards,
)


class StudySessionListCreateView(APIView):
    """
    GET: list recent Study Coach sessions for the current student.
    POST: create a session and generate a static quiz deck.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, "student_profile"):
            return Response(
                {"error": "Only students can use Study Coach"},
                status=status.HTTP_403_FORBIDDEN,
            )
        sessions = StudySession.objects.filter(student=request.user).select_related(
            "lesson", "lesson__course"
        )[:20]
        return Response(StudySessionSerializer(sessions, many=True).data)

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
        cards = generate_static_cards(
            lesson_title=lesson.title or "",
            difficulty_mode=difficulty_mode,
        )
        session = StudySession.objects.create(
            student=request.user,
            lesson=lesson,
            difficulty_mode=difficulty_mode,
            grounding_mode="static",
            status="active",
            cards=cards,
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

        response_text = serializer.validated_data["response"]
        correct = check_card_answer(card, response_text)
        progress = dict(session.progress or default_progress())
        answers = dict(progress.get("answers") or {})
        answers[card_id] = {
            "response": response_text,
            "correct": correct,
            "used_hint_count": serializer.validated_data.get("used_hint_count", 0),
            "flipped": serializer.validated_data.get("flipped", False),
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
