"""
Serializers for lead magnet API.
"""
from django.conf import settings
from rest_framework import serializers
from .models import LeadMagnet, LeadMagnetSubmission


def get_guide_url(slug):
    base = getattr(settings, "LEAD_MAGNET_GUIDE_BASE_URL", "https://www.sbtyacademy.com").rstrip("/")
    return f"{base}/guide/{slug}"


class LeadMagnetPublicSerializer(serializers.ModelSerializer):
    """Public guide data for GET /api/lead-magnet/<slug>/"""
    guide_url = serializers.SerializerMethodField()

    class Meta:
        model = LeadMagnet
        fields = ["title", "description", "benefits", "preview_image_url", "guide_url"]

    def get_guide_url(self, obj):
        return get_guide_url(obj.slug)


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
