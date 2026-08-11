from rest_framework import serializers

from .models import StudySession


class StudySessionCreateSerializer(serializers.Serializer):
    lesson_id = serializers.UUIDField()
    difficulty_mode = serializers.ChoiceField(
        choices=["easy", "hard", "auto"],
        default="easy",
    )
    card_count = serializers.IntegerField(required=False, min_value=3, max_value=20, default=6)


class StudySessionExtendSerializer(serializers.Serializer):
    card_count = serializers.IntegerField(required=False, min_value=1, max_value=20, default=6)


class StudySessionAnswerSerializer(serializers.Serializer):
    card_id = serializers.UUIDField()
    # Blank allowed so Next can auto-grade a skipped card as incorrect.
    response = serializers.CharField(allow_blank=True, max_length=2000)
    used_hint_count = serializers.IntegerField(required=False, min_value=0, default=0)
    flipped = serializers.BooleanField(required=False, default=False)


class StudySessionSerializer(serializers.ModelSerializer):
    lesson_id = serializers.UUIDField(source="lesson.id", read_only=True)
    lesson_title = serializers.CharField(source="lesson.title", read_only=True)
    course_id = serializers.UUIDField(source="lesson.course_id", read_only=True)

    class Meta:
        model = StudySession
        fields = [
            "id",
            "lesson_id",
            "lesson_title",
            "course_id",
            "difficulty_mode",
            "grounding_mode",
            "status",
            "cards",
            "progress",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class StudySessionListSerializer(serializers.ModelSerializer):
    """History list row — omits heavy cards payload."""

    lesson_id = serializers.UUIDField(source="lesson.id", read_only=True)
    lesson_title = serializers.CharField(source="lesson.title", read_only=True)
    course_id = serializers.UUIDField(source="lesson.course_id", read_only=True)
    card_count = serializers.SerializerMethodField()

    class Meta:
        model = StudySession
        fields = [
            "id",
            "lesson_id",
            "lesson_title",
            "course_id",
            "difficulty_mode",
            "grounding_mode",
            "status",
            "card_count",
            "progress",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_card_count(self, obj) -> int:
        cards = obj.cards or []
        return len(cards) if isinstance(cards, list) else 0
