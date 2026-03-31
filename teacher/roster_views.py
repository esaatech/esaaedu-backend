from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from teacher.roster_serializers import (
    TeacherRosterDetailSerializer,
    TeacherRosterListSerializer,
)
from teacher.services.roster import get_teacher_roster_detail, get_teacher_roster_queryset


class StaffTeacherRosterListView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        q = request.query_params.get("q")
        focus_id_raw = request.query_params.get("focus")
        focus_id = int(focus_id_raw) if (focus_id_raw and focus_id_raw.isdigit()) else None

        teachers = get_teacher_roster_queryset(q=q, focus_id=focus_id)
        payload = TeacherRosterListSerializer(teachers, many=True).data
        return Response({"results": payload})


class StaffTeacherRosterDetailView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, teacher_id: int):
        teacher = get_teacher_roster_detail(teacher_id)
        if not teacher:
            raise Http404("Teacher not found")
        payload = TeacherRosterDetailSerializer(teacher).data
        return Response(payload)


@method_decorator(staff_member_required, name="dispatch")
class StaffTeacherRosterPageView(TemplateView):
    template_name = "staff/teachers/teachers_page.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        focus_id_raw = self.request.GET.get("focus")
        focus_id = int(focus_id_raw) if (focus_id_raw and focus_id_raw.isdigit()) else None
        teachers = get_teacher_roster_queryset(focus_id=focus_id)
        context["teachers"] = TeacherRosterListSerializer(teachers, many=True).data
        context["focus_id"] = focus_id
        return context
