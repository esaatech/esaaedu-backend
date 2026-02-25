"""
Serializers for lead magnet API.
"""
from rest_framework import serializers
from .models import LeadMagnet, LeadMagnetSubmission


class LeadMagnetPublicSerializer(serializers.ModelSerializer):
    """Public guide data for GET /api/lead-magnet/<slug>/"""
    class Meta:
        model = LeadMagnet
        fields = ["title", "description", "benefits", "preview_image_url"]


class LeadMagnetSubmitSerializer(serializers.Serializer):
    """Payload for POST /api/lead-magnet/<slug>/submit/"""
    first_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()

    def validate_first_name(self, value):
        return (value or "").strip() or None

    def validate(self, attrs):
        if not attrs.get("first_name"):
            raise serializers.ValidationError({"first_name": "This field is required."})
        return attrs
