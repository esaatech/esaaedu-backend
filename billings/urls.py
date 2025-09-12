from django.urls import path
from .views import CreateCheckoutSessionView, ListMySubscriptionsView, CancelSubscriptionView, StripeWebhookView, CreatePaymentIntentView, ConfirmEnrollmentView, CancelIncompleteSubscriptionView


app_name = 'billing'


urlpatterns = [
    path('courses/<uuid:course_id>/checkout-session/', CreateCheckoutSessionView.as_view(), name='billing-checkout-session'),
    path('courses/<uuid:course_id>/payment-intent/', CreatePaymentIntentView.as_view(), name='billing-payment-intent'),
    path('courses/<uuid:course_id>/cancel-subscription/', CancelIncompleteSubscriptionView.as_view(), name='cancel-incomplete-subscription'),
    path('courses/<uuid:course_id>/confirm-enrollment/', ConfirmEnrollmentView.as_view(), name='confirm-enrollment'),
    path('subscriptions/me/', ListMySubscriptionsView.as_view(), name='billing-subscriptions-me'),
    path('subscriptions/<uuid:subscription_id>/cancel/', CancelSubscriptionView.as_view(), name='billing-subscription-cancel'),
    path('webhooks/stripe/', StripeWebhookView.as_view(), name='billing-stripe-webhook'),
]


