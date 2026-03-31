from __future__ import annotations

from datetime import datetime, timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from courses.admin_class_detail import build_class_detail_context
from courses.models import Class
from teacher.calendar_serializers import StaffClassDialogSerializer
from teacher.services.calendar import get_week_calendar_data, serialize_calendar_events


def _apply_side_by_side_columns(day_events: list[dict]) -> None:
    """
    Place events that start within 30 minutes of each other side-by-side.

    - Events in the same cluster share the same vertical band (top/height)
      based on the earliest start and latest end in the cluster so that they
      truly sit on the same "row" in the grid.
    - Within that band they are laid out in equal-width columns using
      left_pct/width_pct.

    Mutates each event in-place.
    """
    if not day_events:
        return

    THIRTY_MIN = 30
    clusters: list[list[dict]] = []
    cluster: list[dict] = []
    first_start: int | None = None

    for ev in day_events:
        sm = ev.get("_start_minutes")
        if sm is None:
            continue
        if not cluster:
            cluster = [ev]
            first_start = sm
            continue
        if first_start is not None and sm - first_start <= THIRTY_MIN:
            cluster.append(ev)
        else:
            clusters.append(cluster)
            cluster = [ev]
            first_start = sm
    if cluster:
        clusters.append(cluster)

    for cl in clusters:
        # Determine shared vertical band for the whole cluster
        tops = [ev.get("top_pct", 0.0) for ev in cl]
        bottoms = [ev.get("top_pct", 0.0) + ev.get("height_pct", 0.0) for ev in cl]
        if not tops or not bottoms:
            continue
        cluster_top = min(tops)
        cluster_bottom = max(bottoms)
        cluster_height = max(0.0, cluster_bottom - cluster_top)

        cols = max(1, len(cl))
        for idx, ev in enumerate(cl):
            ev["top_pct"] = round(cluster_top, 3)
            ev["height_pct"] = round(cluster_height, 3)
            ev["left_pct"] = round((idx / cols) * 100, 3)
            ev["width_pct"] = round((1 / cols) * 100, 3)


class StaffCalendarWeekApiView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        start_date = request.query_params.get("start_date")
        tz_name = request.query_params.get("tz")
        meta, events = get_week_calendar_data(request, start_date_raw=start_date, tz_name=tz_name)
        payload = serialize_calendar_events(events)
        return Response(
            {
                "week_start": meta.week_start.isoformat(),
                "week_end": meta.week_end.isoformat(),
                "timezone": meta.tz_name,
                "results": payload,
            }
        )


class StaffClassDialogApiView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, class_id):
        class_obj = get_object_or_404(
            Class.objects.select_related("course", "teacher"),
            pk=class_id,
        )
        ctx = build_class_detail_context(class_obj)
        dialog_html = render_to_string(
            "staff/calendar/_class_detail_body.html",
            ctx,
            request=request,
        )
        teacher_name = (
            class_obj.teacher.get_full_name() or class_obj.teacher.email
            if class_obj.teacher_id
            else ""
        )
        payload = {
            "class_id": str(class_obj.id),
            "class_name": class_obj.name,
            "course_title": class_obj.course.title,
            "teacher_name": teacher_name,
            "dialog_html": dialog_html,
        }
        serializer = StaffClassDialogSerializer(payload)
        return Response(serializer.data)


@method_decorator(staff_member_required, name="dispatch")
class StaffCalendarWeekPageView(TemplateView):
    template_name = "staff/calendar/calendar_week_page.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        start_date = self.request.GET.get("start_date")
        tz_name = self.request.GET.get("tz")

        meta, events = get_week_calendar_data(self.request, start_date_raw=start_date, tz_name=tz_name)
        event_payload = serialize_calendar_events(events)

        start_dt_values = [datetime.fromisoformat(e["start_at"]) for e in event_payload]
        end_dt_values = [datetime.fromisoformat(e["end_at"]) for e in event_payload]
        if start_dt_values:
            min_hour = max(0, min(d.hour for d in start_dt_values) - 1)
            max_hour = min(23, max(d.hour for d in end_dt_values) + 1)
        else:
            min_hour, max_hour = 7, 20

        days = [meta.week_start + timedelta(days=i) for i in range(7)]
        events_by_day = {d.isoformat(): [] for d in days}
        for e in event_payload:
            start_dt = datetime.fromisoformat(e["start_at"])
            end_dt = datetime.fromisoformat(e["end_at"])
            day_key = start_dt.date().isoformat()
            if day_key in events_by_day:
                start_minutes = start_dt.hour * 60 + start_dt.minute
                end_minutes = end_dt.hour * 60 + end_dt.minute
                grid_start_minutes = min_hour * 60
                total_grid_minutes = (max_hour - min_hour + 1) * 60
                top_pct = max(0.0, ((start_minutes - grid_start_minutes) / total_grid_minutes) * 100)
                duration_minutes = max(30, end_minutes - start_minutes)
                height_pct = max(4.0, (duration_minutes / total_grid_minutes) * 100)
                e["top_pct"] = round(top_pct, 3)
                e["height_pct"] = round(height_pct, 3)
                e["start_label"] = start_dt.strftime("%I:%M %p")
                e["end_label"] = end_dt.strftime("%I:%M %p")
                e["_start_minutes"] = start_minutes
                e["_end_minutes"] = end_minutes
                events_by_day[day_key].append(e)

        for day_key in events_by_day:
            events_by_day[day_key].sort(key=lambda x: x["start_at"])
            _apply_side_by_side_columns(events_by_day[day_key])

        day_entries = [{"date": d, "events": events_by_day[d.isoformat()]} for d in days]

        context.update(
            {
                "week_start": meta.week_start,
                "week_end": meta.week_end,
                "timezone": meta.tz_name,
                "prev_week_start": meta.week_start - timedelta(days=7),
                "next_week_start": meta.week_start + timedelta(days=7),
                "today_start": datetime.now().date() - timedelta(days=datetime.now().date().weekday()),
                "days": days,
                "day_entries": day_entries,
                "hour_labels": list(range(min_hour, max_hour + 1)),
                "grid_start_hour": min_hour,
                "grid_total_hours": max_hour - min_hour + 1,
            }
        )
        return context
