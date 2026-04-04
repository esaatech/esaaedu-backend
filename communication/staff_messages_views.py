"""Staff-only SMS inbox page + session JSON APIs (IsAdminUser)."""

from __future__ import annotations

import uuid

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from communication.models import SmsRoutingLog
from communication.services.phone import normalize_to_e164
from communication.services.staff_outbound import (
    resolve_staff_compose_phones,
    send_staff_compose_to_user,
    send_staff_reply_from_log,
    send_staff_sms_to_e164,
)
from communication.services.twilio_sms import TwilioNotConfiguredError
from communication.services.staff_sms_ui import (
    SMS_THREAD_MESSAGE_LIMIT,
    admin_queue_thread_summaries,
    contacts_directory_flat_entries,
    conversation_thread_for_anchor,
    delivery_issue_summaries,
    log_to_list_item,
    mark_all_conversation_inbound_read,
    phones_with_admin_queue_unread,
    recent_outbound_delivery_preview,
    teacher_routed_thread_summaries,
)
from users.models import User


def _thread_item(x: SmsRoutingLog) -> dict:
    row = log_to_list_item(x)
    row["body"] = x.body or ""
    if x.direction == SmsRoutingLog.Direction.OUTBOUND:
        row["delivery_status"] = x.delivery_status or ""
        row["delivery_error_code"] = x.delivery_error_code or ""
        row["delivery_error_message"] = x.delivery_error_message or ""
    return row


def _serialize_log_detail(log: SmsRoutingLog) -> dict:
    thread = conversation_thread_for_anchor(
        log,
        limit=SMS_THREAD_MESSAGE_LIMIT,
    )
    return {
        "log": {
            "id": str(log.pk),
            "created_at": log.created_at.isoformat(),
            "direction": log.direction,
            "inbound_routing": log.inbound_routing,
            "read_at": log.read_at.isoformat() if log.read_at else None,
            "student_phone": log.student_phone,
            "twilio_number": log.twilio_number,
            "body": log.body,
            "teacher_id": log.teacher_id,
            "course_id": str(log.course_id) if log.course_id else None,
            "twilio_message_sid": log.twilio_message_sid,
            "related_outbound_id": (
                str(log.related_outbound_id) if log.related_outbound_id else None
            ),
        },
        "thread": [_thread_item(x) for x in thread],
    }


@method_decorator(staff_member_required, name="dispatch")
class StaffMessagesInboxPageView(TemplateView):
    template_name = "staff/messages/inbox_page.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["initial_log_id"] = (self.request.GET.get("log") or "").strip()
        ctx["initial_bucket"] = (self.request.GET.get("bucket") or "").strip()
        return ctx


class StaffMessagesDeliveryIssuesApiView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            limit = int(request.query_params.get("limit") or 25)
        except ValueError:
            limit = 25
        return Response(
            {
                "issues": delivery_issue_summaries(limit=limit),
                "recent_outbound_delivery": recent_outbound_delivery_preview(limit=8),
            }
        )


class StaffMessagesAdminUnreadApiView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            recent_limit = int(request.query_params.get("recent_limit") or 10)
        except ValueError:
            recent_limit = 10
        recent_limit = max(1, min(recent_limit, 50))
        unread_threads, recent_threads = admin_queue_thread_summaries(recent_limit=recent_limit)
        return Response(
            {
                "unread_threads": unread_threads,
                "recent_threads": recent_threads,
            }
        )


class StaffMessagesTeacherUnreadApiView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            recent_offset = int(request.query_params.get("recent_offset") or 0)
        except ValueError:
            recent_offset = 0
        try:
            recent_limit = int(request.query_params.get("recent_limit") or 10)
        except ValueError:
            recent_limit = 10
        recent_offset = max(0, recent_offset)
        recent_limit = max(1, min(recent_limit, 50))
        admin_phones = phones_with_admin_queue_unread()
        unread_threads, recent_threads, has_more = teacher_routed_thread_summaries(
            admin_unread_phones=admin_phones,
            recent_offset=recent_offset,
            recent_limit=recent_limit,
        )
        return Response(
            {
                "unread_threads": unread_threads,
                "recent_threads": recent_threads,
                "recent_has_more": has_more,
                "recent_offset": recent_offset,
                "recent_limit": recent_limit,
                "next_recent_offset": recent_offset + len(recent_threads),
            }
        )


class StaffMessagesLogDetailApiView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, log_id):
        try:
            pk = uuid.UUID(str(log_id))
        except ValueError:
            return Response({"detail": "Invalid log id."}, status=status.HTTP_400_BAD_REQUEST)
        log = get_object_or_404(SmsRoutingLog.objects.all(), pk=pk)
        mark_all_conversation_inbound_read(log)
        log.refresh_from_db(fields=["read_at"])
        return Response(_serialize_log_detail(log))


class StaffMessagesUserSearchApiView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        if len(q) < 2:
            return Response({"results": []})
        role_filter = Q(role=User.Role.STUDENT) | Q(role=User.Role.PARENT) | Q(role=User.Role.TEACHER)
        users = (
            User.objects.filter(role_filter)
            .filter(
                Q(email__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(public_handle__icontains=q)
            )
            .order_by("email")[:25]
        )
        results = []
        for u in users:
            phones = resolve_staff_compose_phones(u)
            results.append(
                {
                    "id": u.pk,
                    "email": u.email,
                    "role": u.role,
                    "display": (u.get_full_name() or "").strip() or u.email,
                    "phones": phones,
                }
            )
        return Response({"results": results})


class StaffMessagesContactsDirectoryApiView(APIView):
    """Flat contact rows (user + one phone line each) for the staff compose picker."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        try:
            limit = int(request.query_params.get("limit") or 500)
        except ValueError:
            limit = 500
        entries = contacts_directory_flat_entries(search=q, limit=limit)
        return Response({"entries": entries})


class StaffMessagesSendApiView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        mode = (request.data.get("mode") or "").strip().lower()
        message = (request.data.get("message") or "").strip()

        if mode == "reply":
            raw_id = request.data.get("log_id")
            try:
                pk = uuid.UUID(str(raw_id))
            except (TypeError, ValueError):
                return Response(
                    {"detail": "log_id must be a UUID."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            log = get_object_or_404(SmsRoutingLog.objects.all(), pk=pk)
            try:
                out = send_staff_reply_from_log(log=log, message_body=message)
            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except TwilioNotConfiguredError:
                return Response(
                    {"detail": "Failed to send SMS (check Twilio configuration)."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return Response(
                {"ok": True, "outbound_log_id": str(out.pk), "twilio_message_sid": out.twilio_message_sid},
                status=status.HTTP_201_CREATED,
            )

        if mode == "compose":
            raw_uid = request.data.get("user_id")
            try:
                uid = int(raw_uid)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "user_id must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            phone_key = request.data.get("phone_key")
            if phone_key is not None:
                phone_key = str(phone_key).strip() or None
            target = get_object_or_404(User.objects.all(), pk=uid)
            try:
                out = send_staff_compose_to_user(
                    target_user=target,
                    message_body=message,
                    phone_key=phone_key,
                )
            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except TwilioNotConfiguredError:
                return Response(
                    {"detail": "Failed to send SMS (check Twilio configuration)."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return Response(
                {"ok": True, "outbound_log_id": str(out.pk), "twilio_message_sid": out.twilio_message_sid},
                status=status.HTTP_201_CREATED,
            )

        if mode == "compose_phone":
            raw_phone = (request.data.get("to_phone") or "").strip()
            if not raw_phone:
                return Response(
                    {"detail": "to_phone is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                normalize_to_e164(raw_phone)
            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            try:
                out = send_staff_sms_to_e164(to_e164=raw_phone, message_body=message)
            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except TwilioNotConfiguredError:
                return Response(
                    {"detail": "Failed to send SMS (check Twilio configuration)."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return Response(
                {"ok": True, "outbound_log_id": str(out.pk), "twilio_message_sid": out.twilio_message_sid},
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {"detail": 'mode must be "reply", "compose", or "compose_phone".'},
            status=status.HTTP_400_BAD_REQUEST,
        )
