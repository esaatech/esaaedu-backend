"""
Serializers for TutorX views
"""
from rest_framework import serializers


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

