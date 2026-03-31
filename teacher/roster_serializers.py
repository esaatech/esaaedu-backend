from urllib.parse import urlencode

from django.urls import NoReverseMatch, reverse
from rest_framework import serializers

from courses.models import Class, Course
from users.models import TeacherPayout, User


def _latest_payout_for_user(obj: User) -> TeacherPayout | None:
    profile = getattr(obj, "teacher_profile", None)
    if not profile:
        return None
    return next(iter(profile.payouts.all()), None)


class TeacherRosterListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    next_pay_day = serializers.SerializerMethodField()
    pay_status = serializers.SerializerMethodField()
    courses_count = serializers.IntegerField(read_only=True)
    classes_active_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "is_active",
            "phone_number",
            "next_pay_day",
            "pay_status",
            "courses_count",
            "classes_active_count",
        ]

    def get_full_name(self, obj):
        return (obj.get_full_name() or "").strip() or obj.email

    def get_phone_number(self, obj):
        profile = getattr(obj, "teacher_profile", None)
        return getattr(profile, "phone_number", None)

    def get_next_pay_day(self, obj):
        payout = _latest_payout_for_user(obj)
        if not payout or not payout.due_date:
            return None
        return payout.due_date.isoformat()

    def get_pay_status(self, obj):
        payout = _latest_payout_for_user(obj)
        return payout.status if payout else None


class StudentLiteSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "full_name"]

    def get_full_name(self, obj):
        return (obj.get_full_name() or "").strip() or obj.email


class ClassDetailSerializer(serializers.ModelSerializer):
    student_count = serializers.IntegerField(read_only=True)
    students = StudentLiteSerializer(many=True, read_only=True)

    class Meta:
        model = Class
        fields = [
            "id",
            "name",
            "is_active",
            "start_date",
            "end_date",
            "max_capacity",
            "student_count",
            "students",
        ]


class CourseDetailSerializer(serializers.ModelSerializer):
    classes = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ["id", "title", "status", "delivery_type", "price", "is_free", "classes"]

    def get_classes(self, obj):
        teacher_id = self.context.get("teacher_id")
        class_rows = [c for c in obj.classes.all() if c.teacher_id == teacher_id]
        return ClassDetailSerializer(class_rows, many=True).data


class TeacherRosterDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    compensation_basis = serializers.SerializerMethodField()
    compensation_rate = serializers.SerializerMethodField()
    next_pay_day = serializers.SerializerMethodField()
    pay_status = serializers.SerializerMethodField()
    teacher_profile_admin_url = serializers.SerializerMethodField()
    user_admin_url = serializers.SerializerMethodField()
    payout_admin_list_url = serializers.SerializerMethodField()
    current_payout = serializers.SerializerMethodField()
    courses = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "is_active",
            "department",
            "phone_number",
            "compensation_basis",
            "compensation_rate",
            "next_pay_day",
            "pay_status",
            "teacher_profile_admin_url",
            "user_admin_url",
            "payout_admin_list_url",
            "current_payout",
            "courses",
        ]

    def get_full_name(self, obj):
        return (obj.get_full_name() or "").strip() or obj.email

    def get_phone_number(self, obj):
        profile = getattr(obj, "teacher_profile", None)
        return getattr(profile, "phone_number", None)

    def get_department(self, obj):
        profile = getattr(obj, "teacher_profile", None)
        return getattr(profile, "department", None)

    def get_compensation_basis(self, obj):
        profile = getattr(obj, "teacher_profile", None)
        return getattr(profile, "compensation_basis", None)

    def get_compensation_rate(self, obj):
        profile = getattr(obj, "teacher_profile", None)
        value = getattr(profile, "compensation_rate", None)
        return str(value) if value is not None else None

    def get_next_pay_day(self, obj):
        payout = _latest_payout_for_user(obj)
        if not payout or not payout.due_date:
            return None
        return payout.due_date.isoformat()

    def get_pay_status(self, obj):
        payout = _latest_payout_for_user(obj)
        return payout.status if payout else None

    def get_teacher_profile_admin_url(self, obj):
        profile = getattr(obj, "teacher_profile", None)
        if not profile:
            return None
        try:
            return reverse("admin:users_teacherprofile_change", args=[profile.pk])
        except NoReverseMatch:
            return None

    def get_user_admin_url(self, obj):
        try:
            return reverse("admin:users_user_change", args=[obj.pk])
        except NoReverseMatch:
            return None

    def get_payout_admin_list_url(self, obj):
        profile = getattr(obj, "teacher_profile", None)
        try:
            base = reverse("admin:users_teacherpayout_changelist")
        except NoReverseMatch:
            return None
        if not profile:
            return base
        return f"{base}?{urlencode({'teacher_profile__id__exact': profile.pk})}"

    def get_current_payout(self, obj):
        payout = _latest_payout_for_user(obj)
        if payout is None:
            return None
        return {
            "id": payout.pk,
            "status": payout.status,
            "amount": str(payout.amount) if payout.amount is not None else None,
            "due_date": payout.due_date.isoformat() if payout.due_date else None,
            "payment_method": payout.payment_method,
            "paid_at": payout.paid_at.isoformat() if payout.paid_at else None,
            "receipt_image_url": payout.receipt_image_url or None,
            "third_party_payment_url": payout.third_party_payment_url or None,
            "notes": payout.notes or None,
        }

    def get_courses(self, obj):
        return CourseDetailSerializer(
            obj.created_courses.all(),
            many=True,
            context={"teacher_id": obj.pk},
        ).data
