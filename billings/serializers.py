from rest_framework import serializers

from billings.models import Payment
from billings.services.payments import payment_is_manual


class PaymentListSerializer(serializers.ModelSerializer):
    """
    Stable JSON shape for staff payment list and agent/tool consumers.
    Keep in sync with billings/schemas/payment_list_item.schema.json.
    """

    user = serializers.SerializerMethodField()
    course = serializers.SerializerMethodField()
    enrolled_course_id = serializers.IntegerField(allow_null=True, read_only=True)
    is_manual = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            'id',
            'user',
            'course',
            'enrolled_course_id',
            'amount',
            'currency',
            'status',
            'paid_at',
            'created_at',
            'is_manual',
        ]

    def get_user(self, obj: Payment):
        u = obj.user
        return {'id': u.pk, 'email': u.email}

    def get_course(self, obj: Payment):
        if obj.course_id is None:
            return None
        c = obj.course
        return {'id': str(c.pk), 'title': c.title}

    def get_is_manual(self, obj: Payment) -> bool:
        return payment_is_manual(obj)
