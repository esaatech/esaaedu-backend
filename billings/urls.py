from django.urls import path
from .views import CreateCheckoutSessionView, ListMySubscriptionsView, CancelSubscriptionView, StripeWebhookView

urlpatterns = [
    path('courses/<uuid:course_id>/checkout-session/', CreateCheckoutSessionView.as_view(), name='billing-checkout-session'),
    path('subscriptions/me/', ListMySubscriptionsView.as_view(), name='billing-subscriptions-me'),
    path('subscriptions/<uuid:subscription_id>/cancel/', CancelSubscriptionView.as_view(), name='billing-subscription-cancel'),
    path('webhooks/stripe/', StripeWebhookView.as_view(), name='billing-stripe-webhook'),
]


