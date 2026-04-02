from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from communication.models import SmsRoutingLog
from communication.services.inbound_processing import process_inbound_sms_routing

User = get_user_model()


class InboundSmsCorrelationTests(TestCase):
    """Correlation: same student_phone + twilio_number, optional reply max age."""

    def setUp(self):
        self.student_phone = "+15550001111"
        self.twilio_number = "+15550002222"

    @override_settings(COMMUNICATION_SMS_REPLY_MAX_AGE_SECONDS=3600)
    def test_recent_outbound_routes_and_sets_related_outbound(self):
        outbound = SmsRoutingLog.objects.create(
            twilio_number=self.twilio_number,
            student_phone=self.student_phone,
            direction=SmsRoutingLog.Direction.OUTBOUND,
            body="Teacher message",
            twilio_message_sid="SMOUTRECENT01",
        )
        inbound = SmsRoutingLog.objects.create(
            twilio_number=self.twilio_number,
            student_phone=self.student_phone,
            direction=SmsRoutingLog.Direction.INBOUND,
            body="Reply",
            twilio_message_sid="SMINRECENT01",
            inbound_routing=SmsRoutingLog.InboundRouting.PENDING,
        )
        process_inbound_sms_routing(inbound.id)
        inbound.refresh_from_db()
        self.assertEqual(inbound.inbound_routing, SmsRoutingLog.InboundRouting.ROUTED)
        self.assertEqual(inbound.related_outbound_id, outbound.id)

    @override_settings(COMMUNICATION_SMS_REPLY_MAX_AGE_SECONDS=3600)
    def test_outbound_older_than_window_is_generic_admin(self):
        outbound = SmsRoutingLog.objects.create(
            twilio_number=self.twilio_number,
            student_phone=self.student_phone,
            direction=SmsRoutingLog.Direction.OUTBOUND,
            body="Old",
            twilio_message_sid="SMOUTSTALE01",
        )
        stale_time = timezone.now() - timedelta(hours=3)
        SmsRoutingLog.objects.filter(pk=outbound.pk).update(created_at=stale_time)

        inbound = SmsRoutingLog.objects.create(
            twilio_number=self.twilio_number,
            student_phone=self.student_phone,
            direction=SmsRoutingLog.Direction.INBOUND,
            body="Late reply",
            twilio_message_sid="SMINSTALE01",
            inbound_routing=SmsRoutingLog.InboundRouting.PENDING,
        )
        process_inbound_sms_routing(inbound.id)
        inbound.refresh_from_db()
        self.assertEqual(inbound.inbound_routing, SmsRoutingLog.InboundRouting.GENERIC_ADMIN)
        self.assertIsNone(inbound.related_outbound_id)

    @override_settings(COMMUNICATION_SMS_REPLY_MAX_AGE_SECONDS=0)
    def test_zero_max_age_allows_stale_outbound(self):
        outbound = SmsRoutingLog.objects.create(
            twilio_number=self.twilio_number,
            student_phone=self.student_phone,
            direction=SmsRoutingLog.Direction.OUTBOUND,
            body="Old",
            twilio_message_sid="SMOUTZERO01",
        )
        stale_time = timezone.now() - timedelta(days=7)
        SmsRoutingLog.objects.filter(pk=outbound.pk).update(created_at=stale_time)

        inbound = SmsRoutingLog.objects.create(
            twilio_number=self.twilio_number,
            student_phone=self.student_phone,
            direction=SmsRoutingLog.Direction.INBOUND,
            body="Reply",
            twilio_message_sid="SMINZERO01",
            inbound_routing=SmsRoutingLog.InboundRouting.PENDING,
        )
        process_inbound_sms_routing(inbound.id)
        inbound.refresh_from_db()
        self.assertEqual(inbound.inbound_routing, SmsRoutingLog.InboundRouting.ROUTED)
        self.assertEqual(inbound.related_outbound_id, outbound.id)


class TeacherSmsInboundReadApiTests(APITestCase):
    """Mark-read and unread-count for inbound SmsRoutingLog (teacher only)."""

    def setUp(self):
        self.teacher = User.objects.create_user(
            firebase_uid="sms_read_teacher_uid",
            email="smsreadteacher@test.com",
            username="smsreadteacher@test.com",
            password="x",
            role=User.Role.TEACHER,
        )
        self.other_teacher = User.objects.create_user(
            firebase_uid="sms_read_other_uid",
            email="smsreadother@test.com",
            username="smsreadother@test.com",
            password="x",
            role=User.Role.TEACHER,
        )

    def test_unread_count_and_mark_read(self):
        unread = SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550001111",
            direction=SmsRoutingLog.Direction.INBOUND,
            body="Hi",
            twilio_message_sid="SMUNREAD01",
            teacher=self.teacher,
            inbound_routing=SmsRoutingLog.InboundRouting.ROUTED,
        )
        SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550003333",
            direction=SmsRoutingLog.Direction.INBOUND,
            body="Other teacher",
            twilio_message_sid="SMOTHER01",
            teacher=self.other_teacher,
            inbound_routing=SmsRoutingLog.InboundRouting.ROUTED,
        )
        self.client.force_authenticate(user=self.teacher)
        r = self.client.get(reverse("teacher_sms_inbound_unread_count"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()["unread_inbound_sms_count"], 1)

        r2 = self.client.patch(
            reverse("teacher_sms_inbound_mark_read", kwargs={"log_id": str(unread.id)})
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertIn("read_at", r2.json())
        unread.refresh_from_db()
        self.assertIsNotNone(unread.read_at)

        r3 = self.client.get(reverse("teacher_sms_inbound_unread_count"))
        self.assertEqual(r3.json()["unread_inbound_sms_count"], 0)

    def test_mark_read_wrong_teacher_404(self):
        log = SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550001111",
            direction=SmsRoutingLog.Direction.INBOUND,
            body="Hi",
            twilio_message_sid="SMWRONG01",
            teacher=self.other_teacher,
            inbound_routing=SmsRoutingLog.InboundRouting.ROUTED,
        )
        self.client.force_authenticate(user=self.teacher)
        r = self.client.patch(
            reverse("teacher_sms_inbound_mark_read", kwargs={"log_id": str(log.id)})
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_read_idempotent(self):
        log = SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550001111",
            direction=SmsRoutingLog.Direction.INBOUND,
            body="Hi",
            twilio_message_sid="SMIDEM01",
            teacher=self.teacher,
            inbound_routing=SmsRoutingLog.InboundRouting.ROUTED,
            read_at=timezone.now(),
        )
        first_read = log.read_at
        self.client.force_authenticate(user=self.teacher)
        r = self.client.patch(
            reverse("teacher_sms_inbound_mark_read", kwargs={"log_id": str(log.id)})
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        log.refresh_from_db()
        self.assertEqual(log.read_at, first_read)
