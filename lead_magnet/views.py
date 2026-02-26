"""
API views for lead magnet: public guide by slug and submit (Brevo + welcome email).
"""
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from .models import LeadMagnet, LeadMagnetSubmission
from .serializers import LeadMagnetPublicSerializer, LeadMagnetSubmitSerializer
from .brevo_client import on_lead_magnet_submit


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
        print(f"[LeadMagnet] Submit request: slug={slug} body={request.data}")

        guide = get_object_or_404(LeadMagnet.objects.filter(is_active=True), slug=slug)
        print(f"[LeadMagnet] Guide found: id={guide.pk} title={guide.title} pdf_url={getattr(guide, 'pdf_url', '') or '(empty)'} brevo_list_id={getattr(guide, 'brevo_list_id', None)}")

        serializer = LeadMagnetSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        first_name = serializer.validated_data["first_name"]
        email = serializer.validated_data["email"]
        print(f"[LeadMagnet] Validated: email={email} first_name={first_name}")

        submission, created = LeadMagnetSubmission.objects.get_or_create(
            lead_magnet=guide,
            email=email,
            defaults={"first_name": first_name},
        )
        if not created:
            submission.first_name = first_name
            submission.save(update_fields=["first_name"])
        print(f"[LeadMagnet] Submission {'created' if created else 'updated'}: id={submission.pk}")

        # Brevo: add to list + send welcome email with PDF link
        print(f"[LeadMagnet] Calling on_lead_magnet_submit(guide={guide.slug}, email={email}, first_name={first_name})")
        on_lead_magnet_submit(guide, email=email, first_name=first_name)
        print("[LeadMagnet] on_lead_magnet_submit returned")

        pdf_url = guide.pdf_url or ""

        if getattr(guide, "email_only_delivery", False):
            pdf_url = ""  # Do not expose PDF URL so frontend does not offer instant download

        print(f"[LeadMagnet] Returning success: pdf_url={pdf_url or '(empty)'}")
        return Response(
            {
                "success": True,
                "message": "Thank you! Check your email for the guide.",
                "pdf_url": pdf_url,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
