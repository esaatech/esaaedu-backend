"""
Serializers for TutorX views
"""
from rest_framework import serializers
from .models import InteractiveVideo, InteractiveEvent


class BlockActionRequestSerializer(serializers.Serializer):
    """
    Serializer for validating block action requests.
    """
    block_content = serializers.CharField(required=True, allow_blank=False)
    block_type = serializers.ChoiceField(
        choices=['text', 'code', 'image', 'diagram'],
        default='text',
        required=False
    )
    context = serializers.DictField(required=False, allow_null=True)
    user_prompt = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    user_prompt_changed = serializers.BooleanField(default=False, required=False)
    temperature = serializers.FloatField(
        min_value=0.0,
        max_value=1.0,
        default=0.7,
        required=False
    )
    max_tokens = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    
    # Action-specific fields
    num_examples = serializers.IntegerField(min_value=1, max_value=10, required=False)
    example_type = serializers.ChoiceField(
        choices=['practical', 'real-world', 'simple', 'advanced'],
        default='practical',
        required=False
    )
    target_level = serializers.ChoiceField(
        choices=['beginner', 'intermediate', 'advanced'],
        default='beginner',
        required=False
    )
    length = serializers.ChoiceField(
        choices=['brief', 'medium', 'detailed'],
        default='brief',
        required=False
    )
    num_questions = serializers.IntegerField(min_value=1, max_value=10, required=False)
    question_types = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_null=True
    )
    
    def validate_block_content(self, value):
        """Validate block content is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("block_content cannot be empty")
        return value.strip()


class ExplainMoreResponseSerializer(serializers.Serializer):
    """Serializer for explain_more action response"""
    explanation = serializers.CharField()
    model = serializers.CharField()


class GiveExamplesResponseSerializer(serializers.Serializer):
    """Serializer for give_examples action response"""
    examples = serializers.ListField(child=serializers.CharField())
    raw_response = serializers.CharField(required=False)
    model = serializers.CharField()


class SimplifyResponseSerializer(serializers.Serializer):
    """Serializer for simplify action response"""
    simplified_content = serializers.CharField()
    model = serializers.CharField()


class SummarizeResponseSerializer(serializers.Serializer):
    """Serializer for summarize action response"""
    summary = serializers.CharField()
    model = serializers.CharField()


class GenerateQuestionsResponseSerializer(serializers.Serializer):
    """Serializer for generate_questions action response"""
    questions = serializers.ListField(
        child=serializers.DictField()
    )
    model = serializers.CharField()


class DrawExplainerImageResponseSerializer(serializers.Serializer):
    """Serializer for draw_explainer_image action response"""
    image_description = serializers.CharField()
    image_prompt = serializers.CharField()
    model = serializers.CharField()


# --- Student Ask AI (sentence-based context) ---

ACTION_TYPE_CHOICES = [
    'explain_more', 'give_examples', 'simplify', 'summarize',
    'generate_questions', 'harder_questions', 'custom',
]


class StudentAskRequestSerializer(serializers.Serializer):
    """Request body for POST /api/tutorx/lessons/<lesson_id>/ask/"""
    lesson_title = serializers.CharField(required=True, allow_blank=False)
    context_before = serializers.CharField(required=False, allow_blank=True, default='')
    current_sentence = serializers.CharField(required=True, allow_blank=False)
    selected_text = serializers.CharField(required=True, allow_blank=False)
    question = serializers.CharField(required=True, allow_blank=False)
    action_type = serializers.ChoiceField(
        choices=ACTION_TYPE_CHOICES,
        required=False,
        allow_null=True
    )

    def validate_lesson_title(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("lesson_title cannot be empty")
        return value.strip()

    def validate_current_sentence(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("current_sentence cannot be empty")
        return value.strip()

    def validate_selected_text(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("selected_text cannot be empty")
        return value.strip()

    def validate_question(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("question cannot be empty")
        return value.strip()


class StudentAskResponseSerializer(serializers.Serializer):
    """Response for POST /api/tutorx/lessons/<lesson_id>/ask/.

    For generate_questions / harder_questions: questions (list), optional message, model.
    For other actions: answer (str), model.
    """
    answer = serializers.CharField(required=False, allow_blank=True)
    questions = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_null=True,
    )
    message = serializers.CharField(required=False, allow_blank=True)
    model = serializers.CharField(required=False, allow_null=True)

    def validate(self, attrs):
        has_answer = attrs.get('answer') is not None and attrs.get('answer') != ''
        has_questions = attrs.get('questions') is not None
        if not has_answer and not has_questions:
            raise serializers.ValidationError("Response must include either 'answer' or 'questions'.")
        return attrs


class LessonChatRequestSerializer(serializers.Serializer):
    """Request for POST /api/tutorx/lessons/<lesson_id>/chat/ (lesson chat window)."""
    message = serializers.CharField(required=True, allow_blank=False)
    conversation = serializers.ListField(
        child=serializers.DictField(allow_null=True),
        required=False,
        default=list,
        help_text='Previous messages: [{ "role": "user"|"assistant", "type"?: "text"|"qanda", "content"?: "...", "data"?: {...} }]',
    )

    def validate_message(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("message cannot be empty")
        return value.strip()


class InteractiveEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = InteractiveEvent
        fields = [
            'id',
            'event_type',
            'timestamp_seconds',
            'title',
            'prompt',
            'explanation',
            'options',
            'correct_option_index',
            'yes_label',
            'no_label',
            'explanation_yes',
            'explanation_no',
            'correct_answer',
            'model_answer',
        ]


class InteractiveVideoSerializer(serializers.ModelSerializer):
    events = InteractiveEventSerializer(many=True)
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = InteractiveVideo
        fields = ['id', 'video_url', 'events']

    def get_video_url(self, obj):
        if obj.audio_video_material:
            return obj.audio_video_material.file_url
        return None


