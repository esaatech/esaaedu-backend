from rest_framework import serializers

from .models import CoachBank, CoachItem, CoachLessonMemory, StudySession
from .services.card_metadata import CARD_DIFFICULTIES, normalize_difficulty, normalize_stored_cards


class StudySessionCreateSerializer(serializers.Serializer):
    lesson_id = serializers.UUIDField()
    difficulty_mode = serializers.ChoiceField(
        choices=["easy", "hard", "auto"],
        default="auto",
    )
    card_count = serializers.IntegerField(required=False, min_value=3, max_value=20, default=6)


class StudySessionExtendSerializer(serializers.Serializer):
    card_count = serializers.IntegerField(required=False, min_value=1, max_value=20, default=6)


class StudySessionAnswerSerializer(serializers.Serializer):
    card_id = serializers.UUIDField()
    response = serializers.CharField(allow_blank=True, max_length=2000)
    used_hint_count = serializers.IntegerField(required=False, min_value=0, default=0)
    flipped = serializers.BooleanField(required=False, default=False)
    advance = serializers.BooleanField(required=False, default=False)


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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["cards"] = normalize_stored_cards(data.get("cards"))
        return data


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


class CoachItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoachItem
        fields = [
            "id",
            "order",
            "question_type",
            "prompt",
            "options",
            "answer",
            "hints",
            "explanation",
            "difficulty",
            "sources",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_question_type(self, value):
        allowed = {choice[0] for choice in CoachItem.QUESTION_TYPE_CHOICES}
        if value not in allowed:
            raise serializers.ValidationError("Invalid question type.")
        return value

    def validate_difficulty(self, value):
        normalized = normalize_difficulty(value)
        if normalized not in CARD_DIFFICULTIES:
            raise serializers.ValidationError("Invalid difficulty.")
        return normalized

    def validate_options(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("options must be a list.")
        return [str(item) for item in value]

    def validate_hints(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("hints must be a list.")
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned or ["Think about what the lesson covers."]

    def validate_sources(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("sources must be a list.")
        return value


class CoachItemWriteSerializer(CoachItemSerializer):
    source_ids = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )

    class Meta(CoachItemSerializer.Meta):
        fields = CoachItemSerializer.Meta.fields + ["source_ids"]


class CoachBankSerializer(serializers.ModelSerializer):
    lesson_id = serializers.UUIDField(source="lesson.id", read_only=True)
    lesson_title = serializers.CharField(source="lesson.title", read_only=True)
    item_count = serializers.SerializerMethodField()
    items = CoachItemSerializer(many=True, read_only=True)

    class Meta:
        model = CoachBank
        fields = [
            "id",
            "lesson_id",
            "lesson_title",
            "item_count",
            "items",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_item_count(self, obj) -> int:
        counted = getattr(obj, "item_count", None)
        if isinstance(counted, int):
            return counted
        return obj.items.count()


class CoachBankGenerateSerializer(serializers.Serializer):
    difficulty_mode = serializers.ChoiceField(
        choices=["easy", "hard", "auto"],
        default="auto",
    )
    card_count = serializers.IntegerField(required=False, min_value=3, max_value=20, default=10)
    source_ids = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )


class CoachLessonMemorySerializer(serializers.ModelSerializer):
    lesson_id = serializers.UUIDField(source="lesson.id", read_only=True)
    lesson_title = serializers.CharField(source="lesson.title", read_only=True)
    course_id = serializers.UUIDField(source="lesson.course_id", read_only=True)
    last_session_id = serializers.UUIDField(read_only=True, allow_null=True)
    study_required = serializers.SerializerMethodField()

    class Meta:
        model = CoachLessonMemory
        fields = [
            "id",
            "lesson_id",
            "lesson_title",
            "course_id",
            "action",
            "auto_rung",
            "next_mix",
            "study_sources",
            "study_cleared_at",
            "study_required",
            "last_feedback",
            "last_band_scores",
            "last_session_id",
            "updated_at",
        ]
        read_only_fields = fields

    def get_study_required(self, obj) -> bool:
        return obj.action == "study_then_retake" and obj.study_cleared_at is None
