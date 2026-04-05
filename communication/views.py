import logging
import uuid

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from communication.models import MessageTemplate, SmsRoutingLog
from communication.services.inbound_processing import process_inbound_sms_routing
from communication.services.outbound import send_teacher_sms_to_student
from communication.services.phone import normalize_to_e164
from communication.services.teacher_outbound_thread import (
    mark_teacher_sms_thread_inbound_read,
    queryset_teacher_sms_thread,
    resolve_teacher_sms_peer_e164,
    serialize_sms_log_row,
)
from communication.services.twilio_delivery import apply_twilio_message_status
from communication.services.twilio_sms import (
    TwilioNotConfiguredError,
    validate_inbound_webhook_signature,
)
from courses.models import Class, Course
from users.models import User

logger = logging.getLogger(__name__)


def communication_health(request):
    """Lightweight check that the communication app URLConf is mounted."""
    return JsonResponse({"app": "communication", "status": "ok"})


class TeacherMessageTemplateListView(APIView):
    """
    GET ?channel=sms|email|whatsapp — active message templates for the teacher UI.
    Frontend substitutes body_template using variables (e.g. course_title from Class.course.title).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not user.is_teacher:
            return Response(
                {"error": "Only teachers can list message templates"},
                status=status.HTTP_403_FORBIDDEN,
            )

        raw = (request.query_params.get("channel") or MessageTemplate.Channel.SMS).lower()
        valid = {c.value for c in MessageTemplate.Channel}
        if raw not in valid:
            return Response(
                {"error": f"channel must be one of: {', '.join(sorted(valid))}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = MessageTemplate.objects.filter(channel=raw, is_active=True).order_by(
            "sort_order", "label"
        )
        templates = [
            {
                "slug": t.slug,
                "label": t.label,
                "body_template": t.body_template,
                "subject_template": t.subject_template or None,
                "variables": t.variables or [],
            }
            for t in qs
        ]
        return Response({"channel": raw, "templates": templates})


class TeacherSmsSendView(APIView):
    """
    POST JSON: student_user_id (int), message (str),
    optional course_id (Course UUID, preferred for Student Management),
    optional class_id (Class UUID, legacy / disambiguation).
    Sends branded SMS via Twilio and records SmsRoutingLog outbound.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.is_teacher:
            return Response(
                {"error": "Only teachers can send SMS"},
                status=status.HTTP_403_FORBIDDEN,
            )

        student_user_id = request.data.get("student_user_id")
        message = (request.data.get("message") or "").strip()
        raw_course_id = request.data.get("course_id")
        raw_class_id = request.data.get("class_id")
        raw_target_phone = (request.data.get("target_phone") or "").strip()
        has_course = raw_course_id not in (None, "")
        has_class = raw_class_id not in (None, "")

        if not student_user_id or not message:
            return Response(
                {"error": "student_user_id and message are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            student_pk = int(student_user_id)
        except (TypeError, ValueError):
            return Response(
                {"error": "student_user_id must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        student = get_object_or_404(User, pk=student_pk, role=User.Role.STUDENT)
        course_arg = None
        course_class = None

        if has_course and has_class:
            try:
                cuid = uuid.UUID(str(raw_course_id))
                clid = uuid.UUID(str(raw_class_id))
            except (ValueError, TypeError):
                return Response(
                    {"error": "course_id and class_id must be UUIDs"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            course_arg = get_object_or_404(Course, id=cuid, teacher=user)
            course_class = get_object_or_404(Class, id=clid, teacher=user)
            if course_class.course_id != course_arg.id:
                return Response(
                    {"error": "class_id does not belong to the given course_id"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif has_class:
            try:
                clid = uuid.UUID(str(raw_class_id))
            except (ValueError, TypeError):
                return Response(
                    {"error": "class_id must be a UUID"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            course_class = get_object_or_404(Class, id=clid, teacher=user)
            course_arg = course_class.course
        elif has_course:
            try:
                cuid = uuid.UUID(str(raw_course_id))
            except (ValueError, TypeError):
                return Response(
                    {"error": "course_id must be a UUID"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            course_arg = get_object_or_404(Course, id=cuid, teacher=user)

        try:
            log = send_teacher_sms_to_student(
                teacher=user,
                student=student,
                message_body=message,
                course=course_arg,
                course_class=course_class,
                target_phone=raw_target_phone or None,
            )
        except PermissionError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except TwilioNotConfiguredError as e:
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(
            {
                "id": str(log.id),
                "twilio_message_sid": log.twilio_message_sid,
                "student_phone": log.student_phone,
            },
            status=status.HTTP_201_CREATED,
        )


def count_teacher_unread_inbound_sms(*, teacher_user) -> int:
    """Inbound SmsRoutingLog rows for this teacher with read_at unset."""
    return SmsRoutingLog.objects.filter(
        direction=SmsRoutingLog.Direction.INBOUND,
        teacher=teacher_user,
        read_at__isnull=True,
    ).count()


class TeacherSmsUnreadCountView(APIView):
    """
    GET — same response shape as teacher conversations unread-count (total_unread, by_recipient_type).
    Used by the React teacher messaging channel badges. SMS rows do not yet split parent vs student;
    recipient_type query param is accepted for API parity but ignored until the model supports it.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not user.is_teacher:
            return Response(
                {"error": "Only teachers can access this endpoint"},
                status=status.HTTP_403_FORBIDDEN,
            )
        # request.query_params.get("recipient_type") — reserved for future filtering
        n = count_teacher_unread_inbound_sms(teacher_user=user)
        return Response(
            {
                "total_unread": n,
                "by_recipient_type": {"parent": 0, "student": 0},
            }
        )


class TeacherSmsInboundUnreadCountView(APIView):
    """
    GET — count inbound SMS rows assigned to this teacher that are not yet read (read_at is null).
    Legacy key unread_inbound_sms_count; prefer GET sms/unread-count/ for app-wide badge parity.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not user.is_teacher:
            return Response(
                {"error": "Only teachers can access this endpoint"},
                status=status.HTTP_403_FORBIDDEN,
            )
        n = count_teacher_unread_inbound_sms(teacher_user=user)
        return Response({"unread_inbound_sms_count": n})


class TeacherSmsInboundMarkReadView(APIView):
    """
    PATCH — set read_at on an inbound SmsRoutingLog for the current teacher.
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request, log_id):
        user = request.user
        if not user.is_teacher:
            return Response(
                {"error": "Only teachers can access this endpoint"},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            lid = uuid.UUID(str(log_id))
        except (ValueError, TypeError):
            return Response({"error": "log_id must be a UUID"}, status=status.HTTP_400_BAD_REQUEST)

        log = get_object_or_404(
            SmsRoutingLog,
            pk=lid,
            direction=SmsRoutingLog.Direction.INBOUND,
            teacher=user,
        )
        if log.read_at is None:
            log.read_at = timezone.now()
            log.save(update_fields=["read_at"])
        return Response(
            {
                "id": str(log.id),
                "read_at": log.read_at.isoformat() if log.read_at else None,
            },
            status=status.HTTP_200_OK,
        )


def _parse_teacher_student_sms_context(
    *,
    user,
    student_id: int,
    params,
):
    """
    Resolve course/class + peer phones for outbound-thread endpoints.
    params: dict-like with .get (QueryDict or merged POST+query).
    Returns (student, student_phone_e164, twilio_e164, course_filter_uuid_or_none).
    Raises ValueError or PermissionError.
    """
    student = get_object_or_404(User, pk=student_id, role=User.Role.STUDENT)

    def _get(key):
        return params.get(key)

    raw_course_id = _get("course_id")
    raw_class_id = _get("class_id")
    has_course = raw_course_id not in (None, "")
    has_class = raw_class_id not in (None, "")

    course_arg = None
    course_class = None

    if has_course and has_class:
        try:
            cuid = uuid.UUID(str(raw_course_id))
            clid = uuid.UUID(str(raw_class_id))
        except (ValueError, TypeError) as e:
            raise ValueError("course_id and class_id must be UUIDs") from e
        course_arg = get_object_or_404(Course, id=cuid, teacher=user)
        course_class = get_object_or_404(Class, id=clid, teacher=user)
        if course_class.course_id != course_arg.id:
            raise ValueError("class_id does not belong to the given course_id")
    elif has_class:
        try:
            clid = uuid.UUID(str(raw_class_id))
        except (ValueError, TypeError) as e:
            raise ValueError("class_id must be a UUID") from e
        course_class = get_object_or_404(Class, id=clid, teacher=user)
        course_arg = course_class.course
    elif has_course:
        try:
            cuid = uuid.UUID(str(raw_course_id))
        except (ValueError, TypeError) as e:
            raise ValueError("course_id must be a UUID") from e
        course_arg = get_object_or_404(Course, id=cuid, teacher=user)

    recipient_type = (_get("recipient_type") or "student").lower()
    if recipient_type not in ("parent", "student"):
        raise ValueError("recipient_type must be parent or student")

    raw_target = (_get("target_phone") or "").strip()

    sp, tw, _rc, _rcl = resolve_teacher_sms_peer_e164(
        teacher=user,
        student=student,
        course=course_arg,
        course_class=course_class,
        recipient_type=recipient_type,
        target_phone=raw_target or None,
    )

    course_filter_uuid = None
    if has_course:
        course_filter_uuid = uuid.UUID(str(raw_course_id))

    return student, sp, tw, course_filter_uuid


class TeacherStudentOutboundThreadView(APIView):
    """
    GET — chronological SMS thread for this teacher, student line, optional course filter.
    Query: channel=sms|email|whatsapp (only sms implemented), recipient_type, course_id, class_id, target_phone.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, student_id):
        user = request.user
        if not user.is_teacher:
            return Response(
                {"error": "Only teachers can access this endpoint"},
                status=status.HTTP_403_FORBIDDEN,
            )

        channel = (request.query_params.get("channel") or "sms").lower()
        if channel in ("email", "whatsapp"):
            return Response(
                {"detail": "not_implemented", "channel": channel, "thread": []},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
        if channel != "sms":
            return Response(
                {"error": "channel must be sms, email, or whatsapp"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            _student, sp, tw, course_filter_uuid = _parse_teacher_student_sms_context(
                user=user,
                student_id=int(student_id),
                params=request.query_params,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except TwilioNotConfiguredError as e:
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        qs = queryset_teacher_sms_thread(
            teacher=user,
            student_phone_e164=sp,
            twilio_number_e164=tw,
            course_id=course_filter_uuid,
        )
        rows = list(qs)
        rows.reverse()
        return Response(
            {
                "channel": "sms",
                "thread": [serialize_sms_log_row(x) for x in rows],
            }
        )


class TeacherStudentOutboundThreadMarkReadView(APIView):
    """
    POST — mark all unread inbound SMS in this thread read (teacher opens Inbox).
    Body or query: channel, recipient_type, course_id, class_id, target_phone (same as GET thread).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, student_id):
        user = request.user
        if not user.is_teacher:
            return Response(
                {"error": "Only teachers can access this endpoint"},
                status=status.HTTP_403_FORBIDDEN,
            )

        channel = (request.data.get("channel") or request.query_params.get("channel") or "sms").lower()
        if channel in ("email", "whatsapp"):
            return Response(
                {"detail": "not_implemented", "channel": channel, "marked": 0},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
        if channel != "sms":
            return Response(
                {"error": "channel must be sms, email, or whatsapp"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        merged = {**request.query_params.dict()}
        for key, val in request.data.items():
            if val is not None and val != "":
                merged[key] = val

        try:
            _student, sp, tw, course_filter_uuid = _parse_teacher_student_sms_context(
                user=user,
                student_id=int(student_id),
                params=merged,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except TwilioNotConfiguredError as e:
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        n = mark_teacher_sms_thread_inbound_read(
            teacher=user,
            student_phone_e164=sp,
            twilio_number_e164=tw,
            course_id=course_filter_uuid,
        )
        return Response({"channel": "sms", "marked": n}, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class TwilioInboundSmsWebhookView(APIView):
    """
    Twilio POST (form): From, To, Body, MessageSid.
    Validates signature, stores inbound SmsRoutingLog, optional inline processing stub.
    """

    permission_classes = []
    authentication_classes = []

    def get(self, request):
        """Browser or uptime probes; Twilio uses POST only."""
        return HttpResponse("Twilio SMS inbound webhook — use POST.", status=200, content_type="text/plain")

    def head(self, request):
        return HttpResponse(status=200)

    def post(self, request):
        if not validate_inbound_webhook_signature(request):
            return HttpResponse("Forbidden", status=403)

        message_sid = (request.POST.get("MessageSid") or "").strip()
        from_raw = (request.POST.get("From") or "").strip()
        to_raw = (request.POST.get("To") or "").strip()
        body = request.POST.get("Body") or ""

        if not message_sid or not from_raw or not to_raw:
            return HttpResponse("Bad Request", status=400)

        if SmsRoutingLog.objects.filter(twilio_message_sid=message_sid).exists():
            return HttpResponse("", status=200)

        try:
            student_phone = normalize_to_e164(from_raw)
            twilio_number = normalize_to_e164(to_raw)
        except ValueError:
            return HttpResponse("Bad Request", status=400)

        log = SmsRoutingLog.objects.create(
            twilio_number=twilio_number,
            student_phone=student_phone,
            teacher=None,
            course=None,
            course_class=None,
            inbound_routing=SmsRoutingLog.InboundRouting.PENDING,
            direction=SmsRoutingLog.Direction.INBOUND,
            body=body,
            twilio_message_sid=message_sid,
            delivery_status="",
            delivery_error_code="",
            delivery_error_message="",
        )

        if getattr(settings, "COMMUNICATION_PROCESS_SMS_INLINE", True):
            try:
                process_inbound_sms_routing(log.id)
            except Exception:
                logger.exception("Inbound SMS inline processing failed log_id=%s", log.id)

        return HttpResponse("", status=200, content_type="text/plain")


@method_decorator(csrf_exempt, name="dispatch")
class TwilioSmsStatusWebhookView(APIView):
    """
    Twilio status callback: MessageSid, MessageStatus, optional ErrorCode / ErrorMessage.
    Point your Twilio number or Messaging Service "Status callback URL" to this path
    (same host as inbound webhook; signature validation uses the full request URL).
    """

    permission_classes = []
    authentication_classes = []

    def post(self, request):
        if not validate_inbound_webhook_signature(request):
            return HttpResponse("Forbidden", status=403)
        sid = (request.POST.get("MessageSid") or "").strip()
        st = (request.POST.get("MessageStatus") or "").strip()
        code = (request.POST.get("ErrorCode") or "").strip()
        err = (request.POST.get("ErrorMessage") or "").strip()[:500]
        if not sid:
            return HttpResponse("Bad Request", status=400)
        n = apply_twilio_message_status(
            message_sid=sid,
            status=st,
            error_code=code,
            error_message=err,
        )
        logger.debug("Twilio SMS status sid=%s status=%s rows_updated=%s", sid, st, n)
        return HttpResponse("", status=200, content_type="text/plain")
