from django.urls import path
from .views import CreateCheckoutSessionView, ListMySubscriptionsView, CancelSubscriptionView
from .views  import StripeWebhookView
from .views import CreatePaymentIntentView, ConfirmEnrollmentView, CancelIncompleteSubscriptionView, BillingDashboardView, DownloadInvoiceView


app_name = 'billing'


urlpatterns = [
    path('courses/<uuid:course_id>/checkout-session/', CreateCheckoutSessionView.as_view(), name='billing-checkout-session'),
    path('courses/<uuid:course_id>/payment-intent/', CreatePaymentIntentView.as_view(), name='billing-payment-intent'),
    path('courses/<uuid:course_id>/cancel-subscription/', CancelIncompleteSubscriptionView.as_view(), name='cancel-incomplete-subscription'),
    path('courses/<uuid:course_id>/confirm-enrollment/', ConfirmEnrollmentView.as_view(), name='confirm-enrollment'),
    path('subscriptions/me/', ListMySubscriptionsView.as_view(), name='billing-subscriptions-me'),
    path('subscriptions/<uuid:subscription_id>/cancel/', CancelSubscriptionView.as_view(), name='billing-subscription-cancel'),
    path('dashboard/', BillingDashboardView.as_view(), name='billing-dashboard'),
    path('payments/<int:payment_id>/download-invoice/', DownloadInvoiceView.as_view(), name='download-invoice'),
    path('webhooks/stripe/', StripeWebhookView.as_view(), name='billing-stripe-webhook'),
]


