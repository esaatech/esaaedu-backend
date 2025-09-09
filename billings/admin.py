from django.contrib import admin
from .models import BillingProduct, BillingPrice, CustomerAccount, Subscription, Payment, WebhookEvent


@admin.register(BillingProduct)
class BillingProductAdmin(admin.ModelAdmin):
    list_display = ("course", "stripe_product_id", "is_active", "created_at")
    search_fields = ("course__title", "stripe_product_id")


@admin.register(BillingPrice)
class BillingPriceAdmin(admin.ModelAdmin):
    list_display = ("product", "billing_period", "unit_amount", "currency", "is_active")
    list_filter = ("billing_period", "is_active", "currency")
    search_fields = ("product__course__title", "stripe_price_id")


@admin.register(CustomerAccount)
class CustomerAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "stripe_customer_id", "created_at")
    search_fields = ("user__email", "stripe_customer_id")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "status", "current_period_end", "cancel_at")
    list_filter = ("status",)
    search_fields = ("user__email", "course__title", "stripe_subscription_id")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "amount", "currency", "status", "paid_at")
    list_filter = ("status", "currency")
    search_fields = ("user__email", "stripe_payment_intent_id", "stripe_invoice_id")


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("stripe_event_id", "type", "processed_at")
    search_fields = ("stripe_event_id", "type")

# Register your models here.
