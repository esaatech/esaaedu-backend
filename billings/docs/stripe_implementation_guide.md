# Complete Stripe Implementation Guide

## Table of Contents
1. [Setup and Configuration](#1-setup-and-configuration)
2. [Stripe CLI for Local Development](#2-stripe-cli-for-local-development)
3. [Creating Products and Prices](#3-creating-products-and-prices)
4. [One-Time Payments](#4-one-time-payments)
5. [Subscription/Installment Payments](#5-subscriptioninstallment-payments)
6. [Webhook Handling](#6-webhook-handling)
7. [Testing and Debugging](#7-testing-and-debugging)

---

## 1. Setup and Configuration

### 1.1 Stripe Account Setup

1. **Create Stripe Account**
   - Go to [https://stripe.com](https://stripe.com)
   - Sign up for a free account
   - Complete account verification

2. **Access Test Mode (Sandbox)**
   - Toggle "Test mode" switch in Stripe Dashboard (top right)
   - Test mode uses `sk_test_` and `pk_test_` keys
   - All transactions are simulated - no real charges

3. **Get API Keys**
   - Navigate to **Developers → API keys**
   - Copy your **Secret key** (`sk_test_...`)
   - Copy your **Publishable key** (`pk_test_...`)
   - ⚠️ **Never commit secret keys to version control**

### 1.2 Django Environment Configuration

Create a `.env` file in your project root:

```bash
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_YOUR_SECRET_KEY_HERE
STRIPE_PUBLISHABLE_KEY=pk_test_YOUR_PUBLISHABLE_KEY_HERE
STRIPE_WEBHOOK_SECRET=whsec_YOUR_WEBHOOK_SECRET_HERE  # For production webhooks
```

### 1.3 Django Settings

In your `settings.py`:

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Stripe Configuration
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
```

### 1.4 Install Required Packages

```bash
pip install stripe python-dotenv
```

---

## 2. Stripe CLI for Local Development

### 2.1 Installation

**macOS:**
```bash
brew install stripe/stripe-cli/stripe
```

**Linux:**
```bash
# Download from https://github.com/stripe/stripe-cli/releases
# Or use package manager
```

**Windows:**
```bash
# Download from https://github.com/stripe/stripe-cli/releases
# Or use Scoop: scoop install stripe
```

### 2.2 Login to Stripe CLI

```bash
stripe login
```

This opens your browser to authorize the CLI with your Stripe account.

### 2.3 Forward Webhooks to Local Server

```bash
stripe listen --forward-to localhost:8000/api/billing/webhooks/stripe/
```

**What this does:**
- Creates a temporary webhook endpoint
- Forwards all Stripe events to your local Django server
- Displays webhook secret: `whsec_...` (save this for testing)
- Shows real-time event logs

**Output example:**
```
> Ready! Your webhook signing secret is whsec_xxxxxxxxxxxxx
> Forwarding events to http://localhost:8000/api/billing/webhooks/stripe/
```

### 2.4 Trigger Test Events

In a separate terminal, trigger test events:

```bash
# Test payment succeeded
stripe trigger payment_intent.succeeded

# Test subscription created
stripe trigger customer.subscription.created

# Test invoice payment succeeded
stripe trigger invoice.payment_succeeded
```

### 2.5 View Event Logs

The CLI shows all events in real-time:
```
2026-01-08 10:00:00   --> payment_intent.created [evt_xxx]
2026-01-08 10:00:01   --> payment_intent.succeeded [evt_yyy]
2026-01-08 10:00:01  <--  [200] POST http://localhost:8000/api/billing/webhooks/stripe/
```

---

## 3. Creating Products and Prices

### 3.1 Understanding Stripe Products and Prices

**Product**: Represents what you're selling (e.g., "Python Course")
**Price**: Represents how much and how often (e.g., "$100 one-time" or "$30/month")

**Key Concepts:**
- One Product can have multiple Prices
- Prices can be one-time or recurring (subscription)
- Prices are immutable (can't change amount) - create new price to update

### 3.2 Product Creation Flow

In your Django project, products are created automatically when a course is created:

```python
# courses/stripe_integration.py

def create_stripe_product_for_course(course):
    """
    Creates Stripe Product and Prices for a course
    """
    stripe_client = get_stripe_client()
    
    # Step 1: Create Stripe Product
    product = stripe_client.Product.create(
        name=course.title,
        description=course.description,
        metadata={
            'course_id': str(course.id),
            'teacher_id': str(course.teacher.id),
            'duration_weeks': course.duration_weeks,
        }
    )
    
    # Step 2: Save Product ID to Database
    billing_product = BillingProduct.objects.create(
        course=course,
        stripe_product_id=product['id'],
        is_active=True
    )
    
    # Step 3: Calculate prices based on course duration
    prices = calculate_course_prices(course.price, course.duration_weeks)
    
    # Step 4: Create One-Time Price
    one_time_price = stripe_client.Price.create(
        product=product['id'],
        unit_amount=int(prices['one_time_price'] * 100),  # Convert to cents
        currency='usd',
        metadata={
            'course_id': str(course.id),
            'billing_type': 'one_time'
        }
    )
    
    # Step 5: Create Monthly Price (if course > 4 weeks)
    if course.duration_weeks > 4:
        monthly_price = stripe_client.Price.create(
            product=product['id'],
            unit_amount=int(prices['monthly_price'] * 100),
            currency='usd',
            recurring={'interval': 'month'},  # Makes it a subscription price
            metadata={
                'course_id': str(course.id),
                'billing_type': 'monthly'
            }
        )
    
    return product
```

### 3.3 Price Calculation Logic

```python
def calculate_course_prices(base_price, duration_weeks):
    """
    Calculate one-time and monthly prices based on course duration
    """
    total_months = math.ceil(duration_weeks / 4)
    
    # One-time price = base price
    one_time_price = base_price
    
    # Monthly price = base price * 1.15 / total_months (15% markup for installments)
    monthly_price = (base_price * 1.15) / total_months
    
    return {
        'one_time_price': one_time_price,
        'monthly_price': monthly_price,
        'total_months': total_months
    }
```

### 3.4 Updating Products and Prices

When course price or duration changes:

```python
def update_stripe_product_for_course(course):
    """
    Update Stripe product and create new prices
    """
    # Step 1: Update Product name/description
    stripe.Product.modify(
        product_id,
        name=course.title,
        description=course.description
    )
    
    # Step 2: Deactivate old prices
    for old_price in existing_prices:
        stripe.Price.modify(old_price.stripe_price_id, active=False)
    
    # Step 3: Create new prices with updated amounts
    # (Same as creation flow)
```

**Important:** Prices are immutable in Stripe. To change a price:
1. Deactivate old price
2. Create new price with new amount
3. Use new price for future payments

### 3.5 Manual Product Creation (Testing)

You can also create products manually via Stripe Dashboard or API:

```python
import stripe

stripe.api_key = "sk_test_..."

# Create Product
product = stripe.Product.create(
    name="Python Course",
    description="Learn Python programming"
)

# Create One-Time Price
one_time_price = stripe.Price.create(
    product=product.id,
    unit_amount=10000,  # $100.00 in cents
    currency='usd'
)

# Create Monthly Subscription Price
monthly_price = stripe.Price.create(
    product=product.id,
    unit_amount=3000,  # $30.00 in cents
    currency='usd',
    recurring={'interval': 'month'}
)
```

---

## 4. One-Time Payments

### 4.1 Overview

One-time payments use Stripe's **PaymentIntent** API. The user pays once and gains immediate access.

### 4.2 Implementation Flow

```
Frontend → Create PaymentIntent → Collect Payment → Confirm Payment → Enrollment
```

### 4.3 Backend: Create PaymentIntent

```python
# billings/views.py

class CreatePaymentIntentView(APIView):
    def post(self, request, course_id: str):
        # Step 1: Get course and pricing
        course = Course.objects.get(id=course_id)
        pricing_type = request.data.get('pricing_type', 'one_time')
        
        # Step 2: Get or create Stripe customer
        customer_account, _ = CustomerAccount.objects.get_or_create(
            user=request.user
        )
        
        if not customer_account.stripe_customer_id:
            stripe_customer = stripe.Customer.create(
                email=request.user.email,
                metadata={'user_id': str(request.user.id)}
            )
            customer_account.stripe_customer_id = stripe_customer.id
            customer_account.save()
        
        # Step 3: Get price from database
        billing_product = BillingProduct.objects.get(course=course)
        price = BillingPrice.objects.get(
            product=billing_product,
            billing_period='one_time',
            is_active=True
        )
        
        # Step 4: Create PaymentIntent
        payment_intent = stripe.PaymentIntent.create(
            amount=int(course.price * 100),  # Convert to cents
            currency='usd',
            customer=customer_account.stripe_customer_id,
            metadata={
                'course_id': str(course.id),
                'user_id': str(request.user.id),
                'pricing_type': 'one_time'
            }
        )
        
        # Step 5: Return client_secret to frontend
        return Response({
            'client_secret': payment_intent.client_secret,
            'intent_type': 'payment',
            'payment_intent_id': payment_intent.id
        })
```

### 4.4 Frontend: Collect Payment

```javascript
// Using Stripe.js
import { loadStripe } from '@stripe/stripe-js';

const stripe = await loadStripe('pk_test_...');

// Create payment intent
const response = await fetch('/api/billing/courses/{id}/payment-intent/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ pricing_type: 'one_time' })
});

const { client_secret } = await response.json();

// Confirm payment
const { error, paymentIntent } = await stripe.confirmCardPayment(client_secret, {
  payment_method: {
    card: cardElement,
    billing_details: { name: 'Customer Name' }
  }
});

if (error) {
  console.error(error);
} else if (paymentIntent.status === 'succeeded') {
  // Payment successful
  console.log('Payment succeeded!');
}
```

### 4.5 Webhook: Handle Payment Success

```python
# billings/views.py

@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    def post(self, request):
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            request.body,
            request.META['HTTP_STRIPE_SIGNATURE'],
            webhook_secret
        )
        
        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            
            # Get metadata
            course_id = payment_intent['metadata']['course_id']
            user_id = payment_intent['metadata']['user_id']
            
            # Create enrollment
            course = Course.objects.get(id=course_id)
            user = User.objects.get(id=user_id)
            
            # Create payment record
            Payment.objects.create(
                user=user,
                course=course,
                stripe_payment_intent_id=payment_intent['id'],
                amount=payment_intent['amount'] / 100,
                currency=payment_intent['currency'],
                status='succeeded'
            )
            
            # Create enrollment
            EnrolledCourse.objects.create(
                student_profile=user.student_profile,
                course=course,
                status='active',
                payment_status='paid'
            )
```

### 4.6 Complete One-Time Payment Flow

1. **User selects course** → Frontend calls `POST /api/billing/courses/{id}/payment-intent/`
2. **Backend creates PaymentIntent** → Returns `client_secret`
3. **Frontend collects card** → Uses Stripe Elements
4. **User confirms payment** → `stripe.confirmCardPayment()`
5. **Stripe processes payment** → Creates `payment_intent.succeeded` event
6. **Webhook received** → Backend creates enrollment and payment record
7. **Frontend confirms** → Calls `POST /api/billing/courses/{id}/confirm-enrollment/`

---

## 5. Subscription/Installment Payments

### 5.1 Overview

Subscriptions use Stripe's **Subscription** API with recurring billing. Users pay monthly until the course is complete.

### 5.2 Key Concepts

- **Subscription**: Recurring payment agreement
- **Setup Intent**: Collects payment method without charging immediately
- **Invoice**: Generated each billing cycle
- **Trial Period**: Optional free period before first charge

### 5.3 Implementation Flow

```
Create Subscription → Collect Payment Method → Setup Intent Succeeds → 
Pay First Invoice → Invoice Payment Succeeds → Enrollment Created
```

### 5.4 Backend: Create Subscription

```python
# billings/views.py

def post(self, request, course_id: str):
    course = Course.objects.get(id=course_id)
    pricing_type = request.data.get('pricing_type', 'monthly')
    trial_period = request.data.get('trial_period', False)
    
    # Get monthly price
    billing_product = BillingProduct.objects.get(course=course)
    monthly_price = BillingPrice.objects.get(
        product=billing_product,
        billing_period='monthly',
        is_active=True
    )
    
    # Calculate subscription duration
    total_months = math.ceil(course.duration_weeks / 4)
    
    # Get trial days if requested
    trial_days = 14 if trial_period else 0
    
    # Create Stripe Subscription
    subscription = stripe.Subscription.create(
        customer=customer_account.stripe_customer_id,
        items=[{'price': monthly_price.stripe_price_id}],
        trial_period_days=trial_days,
        payment_behavior='default_incomplete',  # Requires payment method
        payment_settings={'save_default_payment_method': 'on_subscription'},
        expand=['latest_invoice.payment_intent', 'pending_setup_intent'],
        metadata={
            'course_id': str(course.id),
            'class_id': str(request.data.get('class_id')),
            'pricing_type': 'monthly',
            'trial_period': str(trial_period).lower()
        }
    )
    
    # Get setup intent or payment intent
    if subscription.pending_setup_intent:
        client_secret = subscription.pending_setup_intent.client_secret
        intent_type = 'setup'
    elif subscription.latest_invoice.payment_intent:
        client_secret = subscription.latest_invoice.payment_intent.client_secret
        intent_type = 'payment'
    
    # Create local subscription record
    Subscribers.objects.create(
        user=request.user,
        course=course,
        stripe_subscription_id=subscription.id,
        status='incomplete',  # Will be updated by webhook
        subscription_type='trial' if trial_period else 'monthly'
    )
    
    return Response({
        'client_secret': client_secret,
        'intent_type': intent_type,
        'subscription_id': subscription.id
    })
```

### 5.5 Frontend: Collect Payment Method

```javascript
// For subscriptions, use setup intent
const { client_secret, intent_type, subscription_id } = await response.json();

if (intent_type === 'setup') {
  // Collect payment method for subscription
  const { error, setupIntent } = await stripe.confirmCardSetup(client_secret, {
    payment_method: {
      card: cardElement,
      billing_details: { name: 'Customer Name' }
    }
  });
  
  if (error) {
    console.error(error);
  } else {
    // Payment method saved, subscription will be activated
    console.log('Payment method saved!');
  }
}
```

### 5.6 Webhook: Setup Intent Succeeded

```python
def _handle_setup_intent_succeeded(self, setup_intent):
    """
    Called when payment method is successfully collected
    """
    # Find subscription
    subscription_id = find_subscription_for_setup_intent(setup_intent['id'])
    subscription = stripe.Subscription.retrieve(subscription_id)
    
    # Check if trial period exists
    has_trial = subscription.get('trial_end') is not None
    
    subscriber = Subscribers.objects.get(stripe_subscription_id=subscription_id)
    
    if has_trial:
        # Trial subscription: Set to trialing
        subscriber.status = 'trialing'
        subscriber.save()
        
        # Create enrollment with trial status
        create_enrollment(subscription, is_trial=True)
    else:
        # Non-trial: Set to active immediately
        subscriber.status = 'active'
        subscriber.save()
        
        # Create enrollment immediately
        create_enrollment(subscription, is_trial=False)
        
        # Attempt to pay first invoice
        latest_invoice = subscription.get('latest_invoice')
        if latest_invoice:
            invoice = stripe.Invoice.retrieve(latest_invoice)
            if invoice.status == 'open':
                stripe.Invoice.pay(invoice.id)
```

### 5.7 Webhook: Invoice Payment Succeeded

```python
def _handle_payment_succeeded(self, invoice):
    """
    Called when invoice is successfully paid
    """
    subscription_id = invoice.get('subscription')
    subscription = stripe.Subscription.retrieve(subscription_id)
    
    subscriber = Subscribers.objects.get(stripe_subscription_id=subscription_id)
    
    # Update subscription status
    subscriber.status = 'active'
    subscriber.subscription_type = 'monthly'  # Update from 'trial' if needed
    
    # Sync invoice dates from Stripe
    subscriber.next_invoice_date = datetime.fromtimestamp(
        subscription['current_period_end'], tz=timezone.utc
    )
    subscriber.next_invoice_amount = subscription['items']['data'][0]['price']['unit_amount'] / 100
    subscriber.save()
    
    # Create payment record
    Payment.objects.create(
        user=subscriber.user,
        course=subscriber.course,
        stripe_invoice_id=invoice['id'],
        amount=invoice['amount_paid'] / 100,
        status='succeeded'
    )
    
    # Ensure enrollment exists
    ensure_enrollment(subscription)
```

### 5.8 Subscription States

- **incomplete**: Payment method not collected yet
- **trialing**: Trial period active, no charge yet
- **active**: Subscription active, payment successful
- **past_due**: Payment failed, retrying
- **canceled**: Subscription canceled

### 5.9 Complete Subscription Flow

1. **User selects monthly plan** → Frontend calls payment-intent endpoint
2. **Backend creates Subscription** → Returns `setup_intent.client_secret`
3. **Frontend collects payment method** → `stripe.confirmCardSetup()`
4. **Setup intent succeeds** → Webhook: `setup_intent.succeeded`
   - If trial: Status → `trialing`, enrollment created
   - If no trial: Status → `active`, invoice paid, enrollment created
5. **Invoice payment succeeds** → Webhook: `invoice.payment_succeeded`
   - Payment record created
   - Enrollment ensured
6. **Monthly billing** → Stripe automatically charges each month
7. **Subscription ends** → After total months, subscription cancels automatically

---

## 6. Webhook Handling

### 6.1 Webhook Endpoint Setup

```python
# billings/views.py

@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    permission_classes = []  # No authentication for webhooks
    
    def post(self, request):
        # Get webhook secret
        webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        
        # Verify signature
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        event = stripe.Webhook.construct_event(
            request.body,
            sig_header,
            webhook_secret
        )
        
        # Handle event
        event_type = event['type']
        
        if event_type == 'payment_intent.succeeded':
            self._handle_payment_succeeded(event['data']['object'])
        elif event_type == 'setup_intent.succeeded':
            self._handle_setup_intent_succeeded(event['data']['object'])
        elif event_type == 'invoice.payment_succeeded':
            self._handle_invoice_payment_succeeded(event['data']['object'])
        elif event_type == 'customer.subscription.updated':
            self._handle_subscription_updated(event['data']['object'])
        
        return HttpResponse(status=200)
```

### 6.2 Important Webhook Events

| Event | When It Fires | What to Do |
|-------|---------------|------------|
| `payment_intent.succeeded` | One-time payment succeeds | Create enrollment, payment record |
| `setup_intent.succeeded` | Payment method collected | Update subscription status, create enrollment |
| `invoice.payment_succeeded` | Subscription invoice paid | Update subscription, create payment record |
| `invoice.payment_failed` | Payment fails | Update subscription to `past_due` |
| `customer.subscription.updated` | Subscription status changes | Sync subscription status and dates |
| `customer.subscription.deleted` | Subscription canceled | Mark as canceled in database |

### 6.3 Webhook Idempotency

Always check if event was already processed:

```python
event_id = event['id']

if WebhookEvent.objects.filter(stripe_event_id=event_id).exists():
    return HttpResponse("Event already processed", status=200)

# Process event
# ...

# Save event
WebhookEvent.objects.create(
    stripe_event_id=event_id,
    type=event['type'],
    payload=event['data']
)
```

---

## 7. Testing and Debugging

### 7.1 Test Cards

Stripe provides test card numbers:

| Card Number | Description |
|-------------|-------------|
| `4242 4242 4242 4242` | Successful payment |
| `4000 0000 0000 0002` | Card declined |
| `4000 0000 0000 9995` | Insufficient funds |
| `4000 0025 0000 3155` | Requires authentication (3D Secure) |

**Use any:**
- Future expiry date (e.g., 12/25)
- Any 3-digit CVC
- Any ZIP code

### 7.2 Testing Subscriptions

```bash
# Trigger subscription events
stripe trigger customer.subscription.created
stripe trigger setup_intent.succeeded
stripe trigger invoice.payment_succeeded
```

### 7.3 Testing Payment Failures

```bash
# Use test card 4000 0000 0000 0002
# Or trigger failure events
stripe trigger invoice.payment_failed
```

### 7.4 Debugging Tips

1. **Check Webhook Logs**
   ```bash
   stripe listen --forward-to localhost:8000/api/billing/webhooks/stripe/
   ```

2. **View Events in Dashboard**
   - Go to Stripe Dashboard → Developers → Events
   - See all events and their payloads

3. **Check Database State**
   ```python
   # In Django shell
   from billings.models import Subscribers, Payment
   Subscribers.objects.all()
   Payment.objects.all()
   ```

4. **Verify Webhook Signatures**
   - Always verify webhook signatures in production
   - Use webhook secret from Stripe Dashboard

5. **Test Idempotency**
   - Resend same webhook event
   - Should return 200 without duplicate processing

### 7.5 Common Issues and Solutions

**Issue: Webhook not received**
- ✅ Check Stripe CLI is running
- ✅ Verify webhook endpoint URL
- ✅ Check firewall/network settings

**Issue: Payment succeeds but enrollment not created**
- ✅ Check webhook handler logs
- ✅ Verify metadata is passed correctly
- ✅ Check database constraints

**Issue: Subscription stuck in incomplete**
- ✅ Check if setup_intent succeeded
- ✅ Verify payment method was collected
- ✅ Check invoice status in Stripe Dashboard

**Issue: Wrong billing dates**
- ✅ Verify webhook syncs dates from Stripe
- ✅ Check `current_period_end` in subscription object
- ✅ Use fallback to `current_period_end` if `next_invoice_date` missing

---

## 8. Production Checklist

Before going live:

- [ ] Switch to live mode API keys (`sk_live_...`)
- [ ] Configure production webhook endpoint in Stripe Dashboard
- [ ] Set up webhook signing secret
- [ ] Test with real card (small amount)
- [ ] Set up error monitoring (Sentry, etc.)
- [ ] Configure email notifications for failed payments
- [ ] Set up subscription cancellation flow
- [ ] Test subscription renewal flow
- [ ] Verify idempotency handling
- [ ] Set up backup webhook endpoint
- [ ] Document webhook event handling
- [ ] Set up logging and monitoring

---

## 9. Best Practices

1. **Always verify webhook signatures** in production
2. **Make webhook handlers idempotent** (safe to retry)
3. **Use metadata** to pass custom data (course_id, user_id, etc.)
4. **Handle all webhook events** your app depends on
5. **Log all webhook events** for debugging
6. **Test with Stripe CLI** before deploying
7. **Use test mode** for development
8. **Never commit API keys** to version control
9. **Handle payment failures gracefully**
10. **Sync data from Stripe** rather than trusting local state

---

## 10. Resources

- [Stripe API Documentation](https://stripe.com/docs/api)
- [Stripe Testing Guide](https://stripe.com/docs/testing)
- [Stripe Webhooks Guide](https://stripe.com/docs/webhooks)
- [Stripe CLI Documentation](https://stripe.com/docs/stripe-cli)
- [Stripe Dashboard](https://dashboard.stripe.com)

---

## Summary

This guide covers the complete Stripe implementation:

1. **Setup**: Configure Stripe account and API keys
2. **CLI**: Use Stripe CLI for local webhook testing
3. **Products/Prices**: Create and manage products and prices
4. **One-Time Payments**: Implement PaymentIntent flow
5. **Subscriptions**: Implement Subscription flow with setup intents
6. **Webhooks**: Handle all payment events
7. **Testing**: Test with test cards and CLI
8. **Production**: Deploy with proper security and monitoring

Follow this guide step-by-step to implement Stripe payments in your Django application.

