from django.urls import NoReverseMatch, reverse
from rest_framework import serializers

from billings.models import Payment
from billings.services.ledger import (
    class_summary_for_payment,
    classes_for_payment_detail,
    resolved_course_for_payment,
    subscriber_for_payment,
)
from billings.services.payments import payment_is_manual


class PaymentLedgerListSerializer(serializers.ModelSerializer):
    payer_display = serializers.SerializerMethodField()
    user_email = serializers.EmailField(source='user.email', read_only=True)
    course_title = serializers.SerializerMethodField()
    class_summary = serializers.SerializerMethodField()
    is_manual = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            'id',
            'payer_display',
            'user_email',
            'course_title',
            'class_summary',
            'amount',
            'currency',
            'status',
            'paid_at',
            'created_at',
            'is_manual',
        ]

    def get_payer_display(self, obj: Payment) -> str:
        u = obj.user
        return (u.get_full_name() or '').strip() or u.email

    def get_course_title(self, obj: Payment) -> str:
        c = resolved_course_for_payment(obj)
        return c.title if c else ''

    def get_class_summary(self, obj: Payment) -> str:
        pair_map = self.context.get('classes_by_pair') or {}
        return class_summary_for_payment(obj, pair_map)

    def get_is_manual(self, obj: Payment) -> bool:
        return payment_is_manual(obj)


class PaymentLedgerDetailSerializer(serializers.ModelSerializer):
    payer_display = serializers.SerializerMethodField()
    user_detail = serializers.SerializerMethodField()
    course_detail = serializers.SerializerMethodField()
    enrolled_course_detail = serializers.SerializerMethodField()
    subscriber = serializers.SerializerMethodField()
    classes = serializers.SerializerMethodField()
    payment_admin_url = serializers.SerializerMethodField()
    customer_account_stripe_id = serializers.SerializerMethodField()
    is_manual = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            'id',
            'payer_display',
            'user_detail',
            'course_detail',
            'enrolled_course_detail',
            'subscriber',
            'classes',
            'amount',
            'currency',
            'status',
            'paid_at',
            'created_at',
            'stripe_payment_intent_id',
            'stripe_invoice_id',
            'stripe_charge_id',
            'customer_account_stripe_id',
            'payment_admin_url',
            'is_manual',
        ]

    def get_payer_display(self, obj: Payment) -> str:
        u = obj.user
        return (u.get_full_name() or '').strip() or u.email

    def get_user_detail(self, obj: Payment):
        u = obj.user
        detail = {
            'id': u.pk,
            'email': u.email,
            'full_name': (u.get_full_name() or '').strip() or u.email,
            'admin_url': None,
        }
        try:
            detail['admin_url'] = reverse('admin:users_user_change', args=[u.pk])
        except NoReverseMatch:
            pass
        return detail

    def get_course_detail(self, obj: Payment):
        c = resolved_course_for_payment(obj)
        if not c:
            return None
        row = {'id': str(c.pk), 'title': c.title, 'admin_url': None}
        try:
            row['admin_url'] = reverse('admin:courses_course_change', args=[c.pk])
        except NoReverseMatch:
            pass
        return row

    def get_enrolled_course_detail(self, obj: Payment):
        ec = obj.enrolled_course
        if not ec:
            return None
        row = {
            'id': str(ec.pk),
            'status': ec.status,
            'payment_status': ec.payment_status,
            'payment_due_date': ec.payment_due_date.isoformat() if ec.payment_due_date else None,
            'amount_paid': str(ec.amount_paid),
            'completion_date': ec.completion_date.isoformat() if ec.completion_date else None,
            'admin_url': None,
        }
        try:
            row['admin_url'] = reverse('admin:student_enrolledcourse_change', args=[ec.pk])
        except NoReverseMatch:
            pass
        return row

    def get_subscriber(self, obj: Payment):
        sub = subscriber_for_payment(obj)
        if not sub:
            return None
        return {
            'status': sub.status,
            'subscription_type': sub.subscription_type,
            'next_invoice_date': sub.next_invoice_date.isoformat()
            if sub.next_invoice_date
            else None,
            'next_invoice_amount': str(sub.next_invoice_amount)
            if sub.next_invoice_amount is not None
            else None,
            'current_period_end': sub.current_period_end.isoformat()
            if sub.current_period_end
            else None,
            'cancel_at': sub.cancel_at.isoformat() if sub.cancel_at else None,
        }

    def get_classes(self, obj: Payment):
        rows = []
        for cls in classes_for_payment_detail(obj):
            teacher = cls.teacher
            tname = (teacher.get_full_name() or '').strip() or teacher.email
            rows.append(
                {
                    'id': str(cls.pk),
                    'name': cls.name,
                    'is_active': cls.is_active,
                    'start_date': cls.start_date.isoformat() if cls.start_date else None,
                    'end_date': cls.end_date.isoformat() if cls.end_date else None,
                    'teacher_display': tname,
                }
            )
        return rows

    def get_customer_account_stripe_id(self, obj: Payment):
        account = getattr(obj.user, 'customer_account', None)
        if account is None:
            return ''
        return (account.stripe_customer_id or '').strip()

    def get_payment_admin_url(self, obj: Payment):
        try:
            return reverse('admin:billings_payment_change', args=[obj.pk])
        except NoReverseMatch:
            return None

    def get_is_manual(self, obj: Payment) -> bool:
        return payment_is_manual(obj)
