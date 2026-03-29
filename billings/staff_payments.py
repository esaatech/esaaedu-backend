import uuid

from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from billings.serializers import PaymentListSerializer
from billings.services.payments import get_staff_payments_queryset, parse_datetime_query_param


class StaffPaymentsPagination(PageNumberPagination):
    page_size_query_param = 'page_size'
    max_page_size = 100


class StaffPaymentListView(ListAPIView):
    """
    Staff-only paginated list of all Payment rows.
    Same queryset as other staff tools should use (via this HTTP API or service + serializer).
    """

    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = PaymentListSerializer
    pagination_class = StaffPaymentsPagination

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self._payment_filter_error = None
        try:
            self._payment_filters = self._parse_filters(request.query_params)
        except ValueError as e:
            self._payment_filter_error = str(e)
            self._payment_filters = {}

    def get_queryset(self):
        if getattr(self, '_payment_filter_error', None):
            return get_staff_payments_queryset().none()
        return get_staff_payments_queryset(**self._payment_filters)

    def list(self, request, *args, **kwargs):
        if self._payment_filter_error:
            return Response(
                {'detail': self._payment_filter_error},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().list(request, *args, **kwargs)

    def _parse_filters(self, params):
        filters = {}
        status_val = params.get('status')
        if status_val:
            filters['status'] = status_val.strip()

        user_id = params.get('user_id')
        if user_id not in (None, ''):
            try:
                filters['user_id'] = int(user_id)
            except (TypeError, ValueError):
                raise ValueError('user_id must be an integer') from None

        course_id = params.get('course_id')
        if course_id not in (None, ''):
            try:
                filters['course_id'] = uuid.UUID(str(course_id).strip())
            except (ValueError, TypeError, AttributeError):
                raise ValueError('course_id must be a UUID') from None

        enc_id = params.get('enrolled_course_id')
        if enc_id not in (None, ''):
            try:
                filters['enrolled_course_id'] = int(enc_id)
            except (TypeError, ValueError):
                raise ValueError('enrolled_course_id must be an integer') from None

        try:
            paid_after = parse_datetime_query_param(params.get('paid_after'))
            paid_before = parse_datetime_query_param(params.get('paid_before'))
        except ValueError as e:
            raise ValueError(str(e)) from None
        if paid_after is not None:
            filters['paid_after'] = paid_after
        if paid_before is not None:
            filters['paid_before'] = paid_before

        return filters
