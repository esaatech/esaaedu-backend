from django.db import models
from django.conf import settings


class BillingProduct(models.Model):
    """Stripe Product mapped to a Course (one product per course)."""
    course = models.OneToOneField(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='billing_product',
    )
    stripe_product_id = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'billing_products'

    def __str__(self) -> str:
        return f"Product for {self.course.title}"


class BillingPrice(models.Model):
    """Stripe Price for a product (monthly or one-time)."""
    PERIOD_MONTHLY = 'monthly'
    PERIOD_ONE_TIME = 'one_time'
    BILLING_PERIOD_CHOICES = [
        (PERIOD_MONTHLY, 'Monthly'),
        (PERIOD_ONE_TIME, 'One-time'),
    ]

    product = models.ForeignKey(
        BillingProduct,
        on_delete=models.CASCADE,
        related_name='prices',
    )
    stripe_price_id = models.CharField(max_length=255, unique=True)
    billing_period = models.CharField(max_length=20, choices=BILLING_PERIOD_CHOICES)
    currency = models.CharField(max_length=10, default='usd')
    unit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'billing_prices'
        indexes = [
            models.Index(fields=['product', 'is_active']),
        ]

    def __str__(self) -> str:
        return f"{self.product.course.title} - {self.billing_period} {self.unit_amount} {self.currency}"


class CustomerAccount(models.Model):
    """Maps a local user to a Stripe Customer."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer_account')
    stripe_customer_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'billing_customers'

    def __str__(self) -> str:
        return f"Customer {self.user_id}"




class Payment(models.Model):
    """Records one-time payments and invoices from Stripe."""
    STATUS_REQUIRES_PAYMENT_METHOD = 'requires_payment_method'
    STATUS_REQUIRES_CONFIRMATION = 'requires_confirmation'
    STATUS_REQUIRES_ACTION = 'requires_action'
    STATUS_PROCESSING = 'processing'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_CANCELED = 'canceled'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    course = models.ForeignKey('courses.Course', on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    stripe_invoice_id = models.CharField(max_length=255, blank=True)
    stripe_charge_id = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='usd')
    status = models.CharField(max_length=64)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'billing_payments'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['course']),
            models.Index(fields=['status']),
        ]

    def __str__(self) -> str:
        return f"Payment {self.amount} {self.currency} ({self.status})"


class Subscribers(models.Model):
    """Main subscription tracking table - replaces Subscription model."""
    STATUS_ACTIVE = 'active'
    STATUS_TRIALING = 'trialing'
    STATUS_PAST_DUE = 'past_due'
    STATUS_CANCELED = 'canceled'
    STATUS_INCOMPLETE = 'incomplete'
    STATUS_INCOMPLETE_EXPIRED = 'incomplete_expired'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_TRIALING, 'Trialing'),
        (STATUS_PAST_DUE, 'Past due'),
        (STATUS_CANCELED, 'Canceled'),
        (STATUS_INCOMPLETE, 'Incomplete'),
        (STATUS_INCOMPLETE_EXPIRED, 'Incomplete expired'),
    ]

    SUBSCRIPTION_TYPE_MONTHLY = 'monthly'
    SUBSCRIPTION_TYPE_ONE_TIME = 'one_time'
    SUBSCRIPTION_TYPE_TRIAL = 'trial'
    SUBSCRIPTION_TYPE_CHOICES = [
        (SUBSCRIPTION_TYPE_MONTHLY, 'Monthly'),
        (SUBSCRIPTION_TYPE_ONE_TIME, 'One Time'),
        (SUBSCRIPTION_TYPE_TRIAL, 'Trial'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscribers')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='subscribers')
    stripe_subscription_id = models.CharField(max_length=255, unique=True)
    stripe_price_id = models.CharField(max_length=255)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES)
    subscription_type = models.CharField(max_length=20, choices=SUBSCRIPTION_TYPE_CHOICES, default=SUBSCRIPTION_TYPE_MONTHLY)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    next_invoice_date = models.DateTimeField(null=True, blank=True)
    next_invoice_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    billing_interval = models.CharField(max_length=20, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = 'billing_subscribers'
        unique_together = [('user', 'course')]
        indexes = [
            models.Index(fields=['user', 'course']),
            models.Index(fields=['status']),
        ]

    def save(self, *args, **kwargs):
        """Override save to track status changes"""
        # Get the current status before save
        old_status = None
        if self.pk:
            try:
                old_instance = Subscribers.objects.get(pk=self.pk)
                old_status = old_instance.status
            except Subscribers.DoesNotExist:
                pass
        
        # Only log actual status changes
        if self.pk and old_status is not None and old_status != self.status:
            print(f"🔄 SUBSCRIBER STATUS CHANGE: {old_status} → {self.status} (ID: {self.pk})")
        
        # Call the parent save method
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Subscriber {self.user_id} -> {self.course_id} [{self.status}]"


class WebhookEvent(models.Model):
    """Idempotency log of processed Stripe webhooks."""
    stripe_event_id = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=255)
    payload = models.JSONField()
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'billing_webhook_events'

    def __str__(self) -> str:
        return self.stripe_event_id

# Create your models here.
