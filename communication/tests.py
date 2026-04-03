from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from communication.models import SmsRoutingLog
from communication.services.inbound_processing import process_inbound_sms_routing
from communication.services.staff_sms_ui import mark_inbound_read_for_staff_inbox
from users.models import StudentProfile

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


class StaffSmsUiReadTests(TestCase):
    def test_mark_inbound_read_for_staff_inbox_routed(self):
        log = SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550001111",
            direction=SmsRoutingLog.Direction.INBOUND,
            body="Hi",
            twilio_message_sid="SMSTAFFREAD1",
            inbound_routing=SmsRoutingLog.InboundRouting.ROUTED,
        )
        self.assertTrue(mark_inbound_read_for_staff_inbox(log.pk))
        log.refresh_from_db()
        self.assertIsNotNone(log.read_at)


class StaffMessagesApiTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email="staffsms@test.com",
            password="test-pass-staff",
            firebase_uid="staffsms_uid",
            role=User.Role.ADMIN,
        )
        self.teacher_user = User.objects.create_user(
            email="staffsms_teacher@test.com",
            password="test-pass-t",
            firebase_uid="staffsms_teacher_uid",
            role=User.Role.TEACHER,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)

    def test_admin_threads_group_by_phone(self):
        SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550001111",
            direction=SmsRoutingLog.Direction.INBOUND,
            body="First",
            twilio_message_sid="SMGRP01",
            inbound_routing=SmsRoutingLog.InboundRouting.GENERIC_ADMIN,
        )
        SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550001111",
            direction=SmsRoutingLog.Direction.INBOUND,
            body="Second",
            twilio_message_sid="SMGRP02",
            inbound_routing=SmsRoutingLog.InboundRouting.GENERIC_ADMIN,
        )
        url = reverse("staff_messages_admin_unread")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        unread = response.json()["unread_threads"]
        self.assertEqual(len(unread), 1)
        self.assertEqual(unread[0]["unread_count"], 2)

    def test_teacher_threads_hide_phone_with_admin_unread(self):
        """Same number must not appear in teacher unread while admin-queue unread exists."""
        SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550003333",
            direction=SmsRoutingLog.Direction.INBOUND,
            body="Admin",
            twilio_message_sid="SMSX01",
            inbound_routing=SmsRoutingLog.InboundRouting.GENERIC_ADMIN,
        )
        SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550003333",
            direction=SmsRoutingLog.Direction.INBOUND,
            body="Routed",
            twilio_message_sid="SMSX02",
            inbound_routing=SmsRoutingLog.InboundRouting.ROUTED,
        )
        url = reverse("staff_messages_teacher_unread")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        phones = {t["student_phone"] for t in response.json()["unread_threads"]}
        self.assertNotIn("+15550003333", phones)

    def test_log_detail_marks_routed_inbound_read(self):
        log = SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550001111",
            direction=SmsRoutingLog.Direction.INBOUND,
            body="Routed",
            twilio_message_sid="SMAPIDETAIL1",
            inbound_routing=SmsRoutingLog.InboundRouting.ROUTED,
        )
        url = reverse("staff_messages_log_detail", kwargs={"log_id": log.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log.refresh_from_db()
        self.assertIsNotNone(log.read_at)
        self.assertIn("thread", response.json())

    def test_log_detail_marks_all_inbound_in_conversation(self):
        anchor = SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550001111",
            direction=SmsRoutingLog.Direction.INBOUND,
            body="A",
            twilio_message_sid="SMMULTI1",
            inbound_routing=SmsRoutingLog.InboundRouting.GENERIC_ADMIN,
        )
        other = SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550001111",
            direction=SmsRoutingLog.Direction.INBOUND,
            body="B",
            twilio_message_sid="SMMULTI2",
            inbound_routing=SmsRoutingLog.InboundRouting.GENERIC_ADMIN,
        )
        url = reverse("staff_messages_log_detail", kwargs={"log_id": anchor.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        other.refresh_from_db()
        anchor.refresh_from_db()
        self.assertIsNotNone(anchor.read_at)
        self.assertIsNotNone(other.read_at)

    def test_thread_includes_inbound_and_outbound_phone_variants(self):
        SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550001111",
            direction=SmsRoutingLog.Direction.INBOUND,
            body="In",
            twilio_message_sid="SMVARIN",
            inbound_routing=SmsRoutingLog.InboundRouting.GENERIC_ADMIN,
        )
        SmsRoutingLog.objects.create(
            twilio_number="15550002222",
            student_phone="15550001111",
            direction=SmsRoutingLog.Direction.OUTBOUND,
            body="Out",
            twilio_message_sid="SMVAROUT",
            teacher=None,
        )
        anchor = SmsRoutingLog.objects.get(twilio_message_sid="SMVARIN")
        url = reverse("staff_messages_log_detail", kwargs={"log_id": anchor.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        bodies = {t.get("body") for t in response.json()["thread"]}
        self.assertIn("In", bodies)
        self.assertIn("Out", bodies)

    def test_non_staff_forbidden(self):
        self.client.force_authenticate(user=self.teacher_user)
        log = SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550001111",
            direction=SmsRoutingLog.Direction.INBOUND,
            body="X",
            twilio_message_sid="SMAPIDENY1",
            inbound_routing=SmsRoutingLog.InboundRouting.GENERIC_ADMIN,
        )
        url = reverse("staff_messages_log_detail", kwargs={"log_id": log.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delivery_issues_lists_failed_outbound(self):
        bad = SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550001111",
            direction=SmsRoutingLog.Direction.OUTBOUND,
            body="No route",
            twilio_message_sid="SMDELFAIL1",
            delivery_status="failed",
            delivery_error_code="30008",
        )
        SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550009999",
            direction=SmsRoutingLog.Direction.OUTBOUND,
            body="OK",
            twilio_message_sid="SMDELOK1",
            delivery_status="delivered",
        )
        url = reverse("staff_messages_delivery_issues")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        issues = payload["issues"]
        self.assertIn("recent_outbound_delivery", payload)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["default_log_id"], str(bad.pk))
        self.assertEqual(issues[0]["delivery_status"], "failed")
        self.assertEqual(issues[0]["delivery_error_code"], "30008")

    def test_user_search_returns_phones(self):
        student = User.objects.create_user(
            email="searchstu@test.com",
            password="x",
            firebase_uid="searchstu_uid",
            role=User.Role.STUDENT,
            first_name="Search",
            last_name="Student",
        )
        StudentProfile.objects.create(
            user=student,
            child_phone="+15559901001",
            parent_phone="+15559901002",
        )
        url = reverse("staff_messages_user_search")
        response = self.client.get(url, {"q": "searchstu"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json()["results"]
        self.assertTrue(any(r["id"] == student.pk for r in results))
        row = next(r for r in results if r["id"] == student.pk)
        self.assertEqual(len(row["phones"]), 2)

    @patch("communication.services.staff_outbound.send_sms")
    def test_reply_send_creates_outbound(self, mock_send):
        mock_send.return_value = ("SMFAKEREPLY01", "queued")
        log = SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550001111",
            direction=SmsRoutingLog.Direction.INBOUND,
            body="Help",
            twilio_message_sid="SMAPISEND1",
            inbound_routing=SmsRoutingLog.InboundRouting.GENERIC_ADMIN,
        )
        url = reverse("staff_messages_send")
        response = self.client.post(
            url,
            {"mode": "reply", "log_id": str(log.pk), "message": "We can help."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            SmsRoutingLog.objects.filter(
                direction=SmsRoutingLog.Direction.OUTBOUND,
                twilio_message_sid="SMFAKEREPLY01",
            ).exists()
        )

    @patch("communication.services.staff_outbound.send_sms")
    def test_compose_send_creates_outbound(self, mock_send):
        mock_send.return_value = ("SMFAKECOMP01", "queued")
        student = User.objects.create_user(
            email="compostu@test.com",
            password="x",
            firebase_uid="compostu_uid",
            role=User.Role.STUDENT,
        )
        StudentProfile.objects.create(
            user=student,
            child_phone="+15558801234",
        )
        url = reverse("staff_messages_send")
        response = self.client.post(
            url,
            {
                "mode": "compose",
                "user_id": student.pk,
                "message": "Hello from staff",
                "phone_key": "child",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            SmsRoutingLog.objects.filter(
                direction=SmsRoutingLog.Direction.OUTBOUND,
                twilio_message_sid="SMFAKECOMP01",
            ).exists()
        )


class TwilioSmsStatusWebhookTests(TestCase):
    """Twilio status callback updates outbound SmsRoutingLog delivery fields."""

    def setUp(self):
        self.client = Client()

    @patch("communication.views.validate_inbound_webhook_signature", return_value=True)
    def test_status_updates_outbound_row(self, _sig):
        log = SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550001111",
            direction=SmsRoutingLog.Direction.OUTBOUND,
            body="Hi",
            twilio_message_sid="SMSTATUSWEB1",
        )
        url = reverse("twilio-sms-status")
        response = self.client.post(
            url,
            {
                "MessageSid": "SMSTATUSWEB1",
                "MessageStatus": "failed",
                "ErrorCode": "30008",
                "ErrorMessage": "Unknown destination",
            },
        )
        self.assertEqual(response.status_code, 200)
        log.refresh_from_db()
        self.assertEqual(log.delivery_status, "failed")
        self.assertEqual(log.delivery_error_code, "30008")
        self.assertEqual(log.delivery_error_message, "Unknown destination")
        self.assertIsNotNone(log.delivery_updated_at)

    @patch("communication.views.validate_inbound_webhook_signature", return_value=True)
    def test_missing_message_sid_returns_400(self, _sig):
        url = reverse("twilio-sms-status")
        response = self.client.post(url, {"MessageStatus": "failed"})
        self.assertEqual(response.status_code, 400)


class SmsRoutingLogAdminMarkReadTests(TestCase):
    """Opening an admin-queue inbound log in Django admin sets read_at (GET change view)."""

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            email="smslogadmin@test.com",
            password="test-pass-123",
            firebase_uid="smslogadmin_uid",
            role=User.Role.ADMIN,
        )
        self.client.force_login(self.admin_user)

    def test_admin_queue_inbound_get_change_sets_read_at(self):
        log = SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550001111",
            direction=SmsRoutingLog.Direction.INBOUND,
            body="Need admin",
            twilio_message_sid="SMADMINOPEN01",
            inbound_routing=SmsRoutingLog.InboundRouting.GENERIC_ADMIN,
        )
        self.assertIsNone(log.read_at)
        url = reverse("admin:communication_smsroutinglog_change", args=[log.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        log.refresh_from_db()
        self.assertIsNotNone(log.read_at)

    def test_routed_inbound_get_change_does_not_set_read_at(self):
        log = SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550001111",
            direction=SmsRoutingLog.Direction.INBOUND,
            body="Teacher reply",
            twilio_message_sid="SMROUTEDOPEN01",
            inbound_routing=SmsRoutingLog.InboundRouting.ROUTED,
        )
        url = reverse("admin:communication_smsroutinglog_change", args=[log.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        log.refresh_from_db()
        self.assertIsNone(log.read_at)

    def test_second_get_does_not_change_read_at(self):
        log = SmsRoutingLog.objects.create(
            twilio_number="+15550002222",
            student_phone="+15550001111",
            direction=SmsRoutingLog.Direction.INBOUND,
            body="x",
            twilio_message_sid="SMADMINOPEN02",
            inbound_routing=SmsRoutingLog.InboundRouting.PENDING,
        )
        url = reverse("admin:communication_smsroutinglog_change", args=[log.pk])
        self.client.get(url)
        log.refresh_from_db()
        first = log.read_at
        self.assertIsNotNone(first)
        self.client.get(url)
        log.refresh_from_db()
        self.assertEqual(log.read_at, first)
