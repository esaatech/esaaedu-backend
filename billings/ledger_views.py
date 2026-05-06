from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from zoneinfo import ZoneInfo

from users.admin_calendar_tz import resolve_admin_calendar_timezone_detail
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billings.ledger_serializers import (
    PaymentLedgerDetailSerializer,
    PaymentLedgerListSerializer,
)
from billings.services.ledger import (
    classes_by_user_course_pairs,
    get_ledger_succeeded_paid_totals_month_and_ytd,
    get_payment_ledger_detail,
    get_payment_ledger_queryset,
)


def _parse_ledger_limit(raw) -> int:
    choices = (20, 50, 100)
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return choices[0]
    return n if n in choices else choices[0]


@method_decorator(staff_member_required, name='dispatch')
class StaffPaymentLedgerPageView(TemplateView):
    template_name = 'staff/billing/payments_page.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        limit = _parse_ledger_limit(self.request.GET.get('limit'))
        payments = get_payment_ledger_queryset(limit=limit)
        class_map = classes_by_user_course_pairs(payments)
        ctx['payments'] = PaymentLedgerListSerializer(
            payments, many=True, context={'classes_by_pair': class_map}
        ).data
        tz_name, _ = resolve_admin_calendar_timezone_detail(self.request)
        ctx['ledger_totals'] = get_ledger_succeeded_paid_totals_month_and_ytd(
            cal_tz=ZoneInfo(tz_name)
        )
        ctx['limit'] = limit
        ctx['limit_options'] = (20, 50, 100)
        return ctx


class StaffPaymentLedgerDetailView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, payment_id: int):
        p = get_payment_ledger_detail(payment_id)
        if not p:
            raise Http404()
        return Response(PaymentLedgerDetailSerializer(p).data)
