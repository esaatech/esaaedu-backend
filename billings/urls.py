from django.urls import path
from .views import CreateCheckoutSessionView, ListMySubscriptionsView, CancelSubscriptionView
from .views  import StripeWebhookView
from .views import CreatePaymentIntentView, ConfirmEnrollmentView, CancelIncompleteSubscriptionView, BillingDashboardView, DownloadInvoiceView, CancelCourseView, CreateCustomerPortalSessionView


app_name = 'billing'


urlpatterns = [
    # Specific patterns first
    path('customer-portal-session/', CreateCustomerPortalSessionView.as_view(), name='customer-portal-session'),
    path('dashboard/', BillingDashboardView.as_view(), name='billing-dashboard'),
    path('subscriptions/me/', ListMySubscriptionsView.as_view(), name='billing-subscriptions-me'),
    path('webhooks/stripe/', StripeWebhookView.as_view(), name='billing-stripe-webhook'),
    
    # Course-related patterns
    path('courses/<uuid:course_id>/checkout-session/', CreateCheckoutSessionView.as_view(), name='billing-checkout-session'),
    path('courses/<uuid:course_id>/payment-intent/', CreatePaymentIntentView.as_view(), name='billing-payment-intent'),
    path('courses/<uuid:course_id>/cancel-subscription/', CancelIncompleteSubscriptionView.as_view(), name='cancel-incomplete-subscription'),
    path('courses/<uuid:course_id>/confirm-enrollment/', ConfirmEnrollmentView.as_view(), name='confirm-enrollment'),
    
    # Subscription patterns with parameters
    path('subscriptions/<uuid:subscription_id>/cancel/', CancelSubscriptionView.as_view(), name='billing-subscription-cancel'),
    path('subscriptions/<int:subscription_id>/cancel/', CancelCourseView.as_view(), name='cancel-course'),
    
    # Payment patterns
    path('payments/<int:payment_id>/download-invoice/', DownloadInvoiceView.as_view(), name='download-invoice'),
]


