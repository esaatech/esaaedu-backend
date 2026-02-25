"""
API views for lead magnet: public guide by slug and submit (Brevo + welcome email).
"""
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from django.conf import settings
from .models import LeadMagnet, LeadMagnetSubmission
from .serializers import LeadMagnetPublicSerializer, LeadMagnetSubmitSerializer
from .brevo_client import add_contact_to_list, send_welcome_email


class LeadMagnetDetailView(APIView):
    """
    GET /api/lead-magnet/<slug>/
    Return public guide data: title, description, benefits, preview_image_url.
    """
    permission_classes = [AllowAny]

    def get(self, request, slug):
        guide = get_object_or_404(LeadMagnet.objects.filter(is_active=True), slug=slug)
        serializer = LeadMagnetPublicSerializer(guide)
        return Response(serializer.data)


class LeadMagnetSubmitView(APIView):
    """
    POST /api/lead-magnet/<slug>/submit/
    Body: { "first_name": "...", "email": "..." }
    Creates submission, adds contact to Brevo list (if configured), sends welcome email
    with PDF link. Returns success and optionally pdf_url.
    """
    permission_classes = [AllowAny]

    def post(self, request, slug):
        guide = get_object_or_404(LeadMagnet.objects.filter(is_active=True), slug=slug)
        serializer = LeadMagnetSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        first_name = serializer.validated_data["first_name"]
        email = serializer.validated_data["email"]

        submission, created = LeadMagnetSubmission.objects.get_or_create(
            lead_magnet=guide,
            email=email,
            defaults={"first_name": first_name},
        )
        if not created:
            submission.first_name = first_name
            submission.save(update_fields=["first_name"])

        list_id = guide.brevo_list_id
        if not list_id:
            list_id = getattr(settings, "BREVO_LIST_ID", None)
        if list_id:
            add_contact_to_list(email=email, first_name=first_name, list_id=list_id)

        pdf_url = guide.pdf_url or ""
        if pdf_url:
            send_welcome_email(
                to_email=email,
                first_name=first_name,
                pdf_url=pdf_url,
                guide_title=guide.title,
            )

        return Response(
            {
                "success": True,
                "message": "Thank you! Check your email for the guide.",
                "pdf_url": pdf_url,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
