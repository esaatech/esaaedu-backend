# Stripe Trial Subscription Verification Checklist

## Monthly Subscription with Trial - Stripe Dashboard Verification

Use this checklist to verify that a monthly subscription with trial period is correctly configured in Stripe.

---

## 📋 Subscription Details

### Basic Information
- [ ] **Subscription Status**: Should be `trialing` (not `active` or `incomplete`)
- [ ] **Subscription ID**: Copy the subscription ID (starts with `sub_`)
- [ ] **Customer**: Verify correct customer is linked
- [ ] **Created Date**: Matches when subscription was created

### Trial Period
- [ ] **Trial Start**: Date/time is set (should be when subscription was created)
- [ ] **Trial End**: Date/time is set (should be trial_start + trial_days)
- [ ] **Trial Period Days**: Matches your configured trial period (e.g., 14 days)
- [ ] **Current Period Start**: Should match trial_start during trial
- [ ] **Current Period End**: Should match trial_end during trial

### Subscription Items
- [ ] **Price ID**: Should be your monthly recurring price (starts with `price_`)
- [ ] **Product**: Should link to your course product (not a new product)
- [ ] **Billing Interval**: Should be `monthly`
- [ ] **Unit Amount**: Should match your monthly price (in cents, e.g., $30.00 = 3000)
- [ ] **Quantity**: Should be `1`

---

## 💳 Payment Method

### Payment Method Status
- [ ] **Payment Method**: Should show a card (last 4 digits visible)
- [ ] **Payment Method Status**: Should be `active` or `saved`
- [ ] **Payment Method Type**: Should be `card`
- [ ] **Default Payment Method**: Should be set to this card

### Setup Intent
- [ ] **Setup Intent ID**: Should exist (starts with `seti_`)
- [ ] **Setup Intent Status**: Should be `succeeded`
- [ ] **Setup Intent Created**: Should match subscription creation time

---

## 📄 Invoice Status

### Current Invoice (During Trial)
- [ ] **Invoices Section**: May show a $0.00 invoice with status `Paid` (this is the trial invoice)
- [ ] **Upcoming Invoice Section**: Shows preview of invoice that will be billed when trial ends
- [ ] **Upcoming Invoice Amount**: Should match your monthly subscription price
- [ ] **Upcoming Invoice Date**: Should match `trial_end` date
- [ ] **If you click on the invoice in "Invoices" section**: Status should be `draft` (this is normal - it's a draft invoice that will be finalized when trial ends)

### Expected Behavior
- [ ] **Draft Invoice Created**: Stripe creates a draft invoice during trial (this is normal)
- [ ] **Draft Invoice Status**: When opened, shows as `draft` (will be finalized when trial ends)
- [ ] **No Paid Invoice Yet**: During trial, there should be NO paid invoices (only draft)
- [ ] **Invoice Will Be Finalized**: Draft invoice will be automatically finalized when trial ends
- [ ] **Invoice Will Be Charged**: When trial ends, Stripe will finalize and charge the draft invoice
- [ ] **Invoice Date**: Will match `trial_end` timestamp

### Understanding Draft vs Paid Invoices
- **Draft Invoice** (during trial): Created but not finalized, shows $0.00 or preview amount
- **Paid Invoice** (after trial): Created when trial ends, charged immediately, shows actual amount

---

## 🔄 Subscription Lifecycle

### Current State (During Trial)
- [ ] **Status**: `trialing`
- [ ] **Cancel At**: Should be set (if subscription has auto-cancel configured)
- [ ] **Cancel At Period End**: Should be `false` (unless manually set)
- [ ] **Days Until Due**: Should show days remaining in trial

### Metadata
- [ ] **course_id**: Should match your course ID
- [ ] **class_id**: Should match selected class ID
- [ ] **pricing_type**: Should be `monthly`
- [ ] **trial_period**: Should be `true`
- [ ] **user_id**: Should match your user ID
- [ ] **user_email**: Should match customer email

---

## 📊 Billing Information

### Next Invoice
- [ ] **Next Invoice Date**: Should match `trial_end` date
- [ ] **Next Invoice Amount**: Should match monthly subscription price
- [ ] **Billing Cycle**: Should show "Monthly"

### Subscription Schedule
- [ ] **Start Date**: Matches trial_start
- [ ] **First Charge Date**: Should be trial_end (when trial ends)
- [ ] **Recurring Interval**: Monthly
- [ ] **Total Duration**: Should match course duration (e.g., 4 months for 16-week course)

---

## 🎯 Webhook Events

### Events to Verify (in Stripe Dashboard → Developers → Events)

#### During Subscription Creation
- [ ] `customer.subscription.created` - Subscription created
- [ ] `setup_intent.created` - Setup intent created
- [ ] `setup_intent.succeeded` - Payment method collected
- [ ] `customer.subscription.updated` - Status updated to `trialing`
- [ ] `payment_method.attached` - Payment method attached to customer

#### During Trial (No Events Expected)
- [ ] **No invoice events** during trial period
- [ ] **No charge events** during trial period

#### When Trial Ends (Automatic - Stripe Handles)
- [ ] `invoice.created` - Invoice created automatically
- [ ] `invoice.finalized` - Invoice finalized
- [ ] `charge.succeeded` - Payment charged (if successful)
- [ ] `invoice.payment_succeeded` - Invoice paid successfully
- [ ] `customer.subscription.updated` - Status changed to `active`

---

## ⚠️ Red Flags (Things That Indicate Problems)

### Status Issues
- [ ] ❌ Status is `incomplete` (should be `trialing`)
- [ ] ❌ Status is `past_due` (should be `trialing`)
- [ ] ❌ Status is `canceled` (unless intentionally canceled)

### Product/Price Issues
- [ ] ❌ New product created (should use existing course product)
- [ ] ❌ Price doesn't match monthly subscription price
- [ ] ❌ Price is one-time instead of recurring

### Payment Method Issues
- [ ] ❌ No payment method attached
- [ ] ❌ Setup intent status is not `succeeded`
- [ ] ❌ Payment method is not set as default

### Invoice Issues
- [ ] ❌ Invoice created immediately (should wait until trial ends)
- [ ] ❌ Invoice amount is wrong
- [ ] ❌ Invoice status is `failed` or `void`

### Trial Issues
- [ ] ❌ Trial start/end dates are missing
- [ ] ❌ Trial period days don't match configuration
- [ ] ❌ Trial end date is in the past (trial should be active)

---

## ✅ Expected Values Example

For a **$30/month subscription with 14-day trial**:

```
Subscription:
  Status: trialing
  Trial Start: 2026-01-08 10:00:00 UTC
  Trial End: 2026-01-22 10:00:00 UTC
  Current Period Start: 2026-01-08 10:00:00 UTC
  Current Period End: 2026-01-22 10:00:00 UTC
  
Price:
  Unit Amount: $30.00 (3000 cents)
  Interval: monthly
  Product: [Your Course Product]
  
Payment Method:
  Status: active
  Type: card
  Last 4: [card digits]
  
Invoice:
  Latest Invoice: None (during trial)
  Next Invoice Date: 2026-01-22 10:00:00 UTC
  Next Invoice Amount: $30.00
  
Metadata:
  pricing_type: monthly
  trial_period: true
  course_id: [your course ID]
```

---

## 🔍 Where to Find These in Stripe Dashboard

1. **Subscriptions**: Dashboard → Customers → [Customer] → Subscriptions → [Subscription]
2. **Payment Methods**: Dashboard → Customers → [Customer] → Payment Methods
3. **Invoices**: Dashboard → Customers → [Customer] → Invoices
4. **Events**: Dashboard → Developers → Events
5. **Products**: Dashboard → Products → [Product]
6. **Prices**: Dashboard → Products → [Product] → Prices

---

## 📝 Quick Verification Steps

1. **Go to Subscription**: Dashboard → Customers → Select customer → Subscriptions tab
2. **Check Status**: Should be `trialing` (green badge)
3. **Check Trial Dates**: Trial end should be in the future
4. **Check Payment Method**: Should show card icon with last 4 digits
5. **Check Metadata**: Click "..." → View metadata → Verify course_id, pricing_type, trial_period
6. **Check Price**: Click on price ID → Verify it's monthly recurring, correct amount
7. **Check Product**: Click on product → Verify it's your course product (not a new one)
8. **Check Invoices Section**: 
   - May show $0.00 invoice with "Paid" status (trial invoice - this is normal)
   - If you click on it, status should be `draft` (this is expected)
9. **Check Upcoming Invoice Section**: 
   - Should show preview of invoice that will be billed when trial ends
   - Amount should match monthly subscription price
   - Date should match trial_end date
10. **Check Events**: Developers → Events → Filter by subscription ID → Verify webhook events

---

## 🎯 Success Criteria

A correctly configured trial subscription should have:

✅ Status: `trialing`  
✅ Trial dates set correctly  
✅ Payment method collected and saved  
✅ Using existing course product (not new product)  
✅ Monthly recurring price attached  
✅ Metadata correctly set  
✅ No paid invoices during trial  
✅ Next invoice scheduled for trial_end date  

If all these checkboxes are ✅, your trial subscription is configured correctly!

