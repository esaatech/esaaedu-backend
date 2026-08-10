from rest_framework import serializers

from .models import StudySession


class StudySessionCreateSerializer(serializers.Serializer):
    lesson_id = serializers.UUIDField()
    difficulty_mode = serializers.ChoiceField(
        choices=["easy", "hard", "auto"],
        default="easy",
    )


class StudySessionAnswerSerializer(serializers.Serializer):
    card_id = serializers.UUIDField()
    response = serializers.CharField(allow_blank=False, max_length=2000)
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
