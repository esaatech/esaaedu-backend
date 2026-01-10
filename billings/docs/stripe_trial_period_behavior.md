# Stripe Trial Period - Expected Behavior

## How Stripe Handles Trial Periods

### 1. Subscription Creation with Trial

When you create a subscription with `trial_period_days`:

```python
subscription = stripe.Subscription.create(
    customer=customer_id,
    items=[{'price': price_id}],
    trial_period_days=14,  # 14-day trial
    payment_behavior='default_incomplete'
)
```

**What Stripe Does:**
1. ✅ Creates subscription with status `trialing`
2. ✅ Sets `trial_start` and `trial_end` timestamps
3. ✅ **Does NOT create an invoice immediately**
4. ✅ **Does NOT charge the payment method during trial**
5. ✅ Subscription remains in `trialing` status until trial ends

### 2. During Trial Period

**Subscription Status:** `trialing`

**What Happens:**
- User has access (based on your application logic)
- No charges are made
- No invoices are created
- Payment method is saved but not charged

**Webhooks You'll Receive:**
- `customer.subscription.created` - When subscription is created
- `setup_intent.succeeded` - When payment method is collected
- `customer.subscription.updated` - Status changes to `trialing`

### 3. When Trial Ends (Automatic Behavior)

**Stripe Automatically:**
1. ✅ Creates an invoice (`invoice.created` webhook)
2. ✅ Finalizes the invoice (`invoice.finalized` webhook)
3. ✅ Attempts to charge the payment method
4. ✅ If successful:
   - Sends `invoice.payment_succeeded` webhook
   - Updates subscription status to `active`
   - Sets `current_period_start` and `current_period_end`
5. ✅ If payment fails:
   - Sends `invoice.payment_failed` webhook
   - Subscription status may change to `past_due` or `incomplete`

**You DO NOT Need To:**
- ❌ Manually create invoices
- ❌ Manually charge the payment method
- ❌ Manually update subscription status

**Stripe handles all of this automatically!**

### 4. Expected Webhook Sequence When Trial Ends

```
1. invoice.created (invoice status: draft)
2. invoice.finalized (invoice status: open)
3. charge.succeeded (if payment succeeds)
4. invoice.payment_succeeded (invoice status: paid)
5. customer.subscription.updated (status: trialing → active)
```

### 5. Invoice Timing

**Important:** Invoices are created **at the moment the trial ends**, not before.

- If trial ends on Jan 22 at 3:00 PM UTC
- Invoice is created on Jan 22 at 3:00 PM UTC
- Payment is attempted immediately
- Webhooks are sent within seconds

### 6. Products and Prices - Best Practices

**❌ WRONG - Creates New Product:**
```python
# This creates a NEW product every time
stripe.Price.create(
    product_data={'name': 'Course Name'},  # Creates new product!
    unit_amount=5000,
    currency='usd',
    recurring={'interval': 'month'}
)
```

**✅ CORRECT - Reuse Existing Product:**
```python
# Get existing product
billing_product = BillingProduct.objects.get(course=course)

# Create price using existing product ID
stripe.Price.create(
    product=billing_product.stripe_product_id,  # Use existing product
    unit_amount=5000,
    currency='usd',
    recurring={'interval': 'month'}
)
```

**Why This Matters:**
- One product should represent one course
- Multiple prices can belong to one product (one-time, monthly, etc.)
- Keeps Stripe dashboard organized
- Easier to track revenue per course

### 7. Checking Trial Status

**In Stripe Dashboard:**
- Go to Subscriptions → Select subscription
- Check "Trial period" section
- See `trial_end` timestamp
- Status will show as "Trialing"

**In Your Code:**
```python
subscription = stripe.Subscription.retrieve(subscription_id)

# Check if trial exists
has_trial = subscription.get('trial_end') is not None
trial_end_timestamp = subscription.get('trial_end')

# Check subscription status
status = subscription.status  # 'trialing' during trial
```

### 8. Common Issues and Solutions

**Issue: No invoice when trial ends**
- ✅ **This is normal** - Invoice is created automatically by Stripe
- ✅ Check Stripe Dashboard → Invoices (may take a few seconds)
- ✅ Check webhook logs for `invoice.created` event
- ✅ Verify `stripe listen` is running to receive webhooks

**Issue: New product created for each subscription**
- ❌ **Problem:** Using `product_data` in `Price.create()`
- ✅ **Solution:** Use existing `product_id` instead

**Issue: Trial not ending**
- ✅ Check `trial_end` timestamp in subscription
- ✅ Verify trial period was set correctly (`trial_period_days`)
- ✅ Wait for actual trial end time (Stripe uses UTC)

**Issue: Payment not attempted when trial ends**
- ✅ Check if payment method is attached
- ✅ Check subscription status (should be `trialing`)
- ✅ Verify webhook handlers are working
- ✅ Check Stripe Dashboard for invoice status

### 9. Testing Trial End

**Method 1: Wait for Real Trial End**
- Create subscription with 1-day trial
- Wait 24 hours
- Check for invoice creation

**Method 2: Use Stripe CLI to Trigger Events**
```bash
# Trigger invoice creation (simulates trial end)
stripe trigger invoice.created

# Trigger invoice payment succeeded
stripe trigger invoice.payment_succeeded
```

**Method 3: Update Trial End in Stripe Dashboard**
- Go to subscription in Stripe Dashboard
- Update `trial_end` to a past timestamp
- Stripe will immediately process trial end

### 10. Summary

**Stripe's Automatic Behavior:**
- ✅ Creates subscription in `trialing` status
- ✅ Saves payment method without charging
- ✅ Automatically creates invoice when trial ends
- ✅ Automatically attempts payment when trial ends
- ✅ Updates subscription status automatically
- ✅ Sends webhooks for all events

**Your Application's Responsibility:**
- ✅ Handle webhooks correctly
- ✅ Update local database when status changes
- ✅ Grant/revoke access based on subscription status
- ✅ Use existing products, don't create new ones
- ✅ Monitor webhook events for errors

**Key Takeaway:** Stripe handles the entire trial-to-paid transition automatically. You just need to listen to webhooks and update your database accordingly.

