# Stripe CLI Tutorial: Local Webhook Testing

## Overview

The Stripe CLI is a command-line tool that allows you to test Stripe webhooks locally without deploying to production. It acts as a **proxy/forwarder** between Stripe's servers and your local Django application.

## How It Works

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   Stripe        │         │   Stripe CLI    │         │   Your Local    │
│   Dashboard     │         │   (Terminal)     │         │   Django App    │
│   (Test Mode)   │         │                 │         │   (localhost)   │
└─────────────────┘         └─────────────────┘         └─────────────────┘
       │                            │                            │
       │  1. Payment Event          │                            │
       ├───────────────────────────►│                            │
       │                            │                            │
       │                            │  2. Forward Webhook        │
       │                            ├───────────────────────────►│
       │                            │                            │
       │                            │  3. Process & Return 200   │
       │                            │◄───────────────────────────┤
       │                            │                            │
       │  4. Event Processed        │                            │
       │◄───────────────────────────┤                            │
```

## Key Differences: CLI vs Production Webhooks

### Stripe CLI (Local Development)
- ✅ **Automatic**: No need to configure webhook endpoints in Stripe Dashboard
- ✅ **All Events**: Receives ALL events automatically (no need to select which events to listen for)
- ✅ **Temporary**: Creates a temporary webhook endpoint that only works while CLI is running
- ✅ **Test Mode Only**: Only works with Stripe test mode (sk_test_ keys)
- ✅ **Real-time**: Events are forwarded immediately as they happen

### Production Webhooks (Stripe Dashboard)
- ⚙️ **Manual Setup**: Must configure webhook endpoint URL in Stripe Dashboard
- ⚙️ **Selective**: Must manually select which events to listen for
- ⚙️ **Permanent**: Webhook endpoint persists until you delete it
- ⚙️ **Test or Live**: Can work with both test and live mode
- ⚙️ **Delayed**: Events may arrive with slight delays

## Installation & Setup

### Step 1: Install Stripe CLI

**macOS (using Homebrew):**
```bash
brew install stripe/stripe-cli/stripe
```

**Other platforms:**
Visit: https://stripe.com/docs/stripe-cli

### Step 2: Login to Stripe

```bash
stripe login
```

This will:
1. Open your browser or show a URL
2. Ask you to enter a pairing code
3. Authenticate with your Stripe account
4. Store credentials locally (valid for 90 days)

**Example output:**
```
Your pairing code is: safe-cheer-awards-aver
This pairing code verifies your authentication with Stripe.
Press Enter to open the browser or visit https://dashboard.stripe.com/stripecli/confirm_auth?t=...
> Done! The Stripe CLI is configured for sbtyacademy with account id acct_1S5ec7CIxQdkR5nZ
```

### Step 3: Start Forwarding Webhooks

```bash
stripe listen --forward-to localhost:8000/api/billing/webhooks/stripe/
```

**What this does:**
- `stripe listen`: Starts listening for webhook events from Stripe
- `--forward-to`: Forwards all events to your local Django endpoint
- `localhost:8000/api/billing/webhooks/stripe/`: Your Django webhook URL

**Example output:**
```
> Ready! You are using Stripe API Version [2024-11-20.acacia]. 
Your webhook signing secret is whsec_b02e7f8f539dab1b75a8963afc8e43130faaf5876a6dc24a23291acd0aaed000 (^C to quit)
```

### Step 4: Copy Webhook Secret to .env

Copy the webhook signing secret (starts with `whsec_`) and add it to your `.env` file:

```env
STRIPE_WEBHOOK_SECRET=whsec_b02e7f8f539dab1b75a8963afc8e43130faaf5876a6dc24a23291acd0aaed000
```

**Important:** This secret changes each time you restart `stripe listen`, so update your `.env` file each time.

### Step 5: Start Your Django Server

In a separate terminal:

```bash
python manage.py runserver
```

## Testing Webhooks

### Method 1: Real Payment Flow

1. Make a real payment through your frontend
2. Watch the Stripe CLI terminal - you'll see events being forwarded:

```
2026-01-06 15:55:35   --> customer.subscription.created [evt_1SmiDzCIxQdkR5nZNKZ3A4Gu]
2026-01-06 15:55:35   --> invoice.created [evt_1SmiDzCIxQdkR5nZ8XF6PiO4]
2026-01-06 15:55:36  <--  [200] POST http://localhost:8000/api/billing/webhooks/stripe/ [evt_1SmiDzCIxQdkR5nZNKZ3A4Gu]
```

**Event Flow:**
- `-->` = Event received from Stripe
- `<--` = Response sent back to Stripe (200 = success)

### Method 2: Trigger Test Events

You can trigger specific events manually:

```bash
# Trigger checkout.session.completed
stripe trigger checkout.session.completed

# Trigger setup_intent.succeeded
stripe trigger setup_intent.succeeded

# Trigger customer.subscription.updated
stripe trigger customer.subscription.updated
```

## Events Automatically Received

**Yes!** When using Stripe CLI, you receive **ALL events** automatically. You don't need to configure which events to listen for in the Stripe Dashboard.

### Common Events You'll See:

1. **Payment Flow Events:**
   - `setup_intent.created` - Setup intent created
   - `setup_intent.succeeded` - Payment method collected successfully
   - `payment_method.attached` - Payment method attached to customer
   - `customer.subscription.created` - Subscription created
   - `customer.subscription.updated` - Subscription status changed
   - `invoice.created` - Invoice created
   - `invoice.payment_succeeded` - Payment succeeded
   - `invoice.upcoming` - Upcoming invoice notification

2. **Checkout Flow Events:**
   - `checkout.session.completed` - Checkout completed
   - `checkout.session.async_payment_succeeded` - Async payment succeeded

3. **Subscription Management:**
   - `customer.subscription.deleted` - Subscription canceled
   - `customer.subscription.trial_will_end` - Trial ending soon

## Monitoring Webhook Events

### In Stripe CLI Terminal

Watch events in real-time:

```
2026-01-06 15:55:35   --> customer.subscription.created [evt_1SmiDzCIxQdkR5nZNKZ3A4Gu]
2026-01-06 15:55:35   --> invoice.created [evt_1SmiDzCIxQdkR5nZ8XF6PiO4]
2026-01-06 15:55:36  <--  [200] POST http://localhost:8000/api/billing/webhooks/stripe/ [evt_1SmiDzCIxQdkR5nZNKZ3A4Gu]
```

### In Django Server Logs

Check your Django console for webhook processing:

```
🎣 Processing webhook event: customer.subscription.updated (evt_1SmiEHCIxQdkR5nZVfC397NZ)
✅ Successfully processed webhook: customer.subscription.updated
```

## Troubleshooting

### Issue: "Webhook secret not configured"

**Solution:** Make sure you've added the webhook secret from `stripe listen` to your `.env` file.

### Issue: "Invalid signature"

**Solution:** The webhook secret changed. Restart `stripe listen` and update your `.env` file with the new secret.

### Issue: Events not arriving

**Check:**
1. Is `stripe listen` running?
2. Is your Django server running?
3. Are you using test mode API keys? (CLI only works with test mode)
4. Is the forward URL correct? (`localhost:8000/api/billing/webhooks/stripe/`)

### Issue: "Connection refused"

**Solution:** Make sure your Django server is running on port 8000 before starting `stripe listen`.

## Best Practices

1. **Keep CLI Running:** Leave `stripe listen` running in a separate terminal while developing
2. **Update Secret:** Remember to update `.env` when restarting `stripe listen`
3. **Test Mode Only:** CLI only works with test mode - use `sk_test_` keys
4. **Monitor Both Terminals:** Watch both Stripe CLI and Django server logs
5. **Use Test Cards:** Use Stripe test card numbers (4242 4242 4242 4242) for testing

## Comparison: CLI vs Production

| Feature | Stripe CLI | Production Dashboard |
|---------|-----------|----------------------|
| Setup | Automatic | Manual configuration |
| Events | All events | Selected events only |
| Endpoint | Temporary | Permanent |
| Mode | Test only | Test or Live |
| Secret | Changes on restart | Static |
| Use Case | Local development | Production |

## Summary

**Stripe CLI is perfect for local development because:**
- ✅ No Dashboard configuration needed
- ✅ Receives all events automatically
- ✅ Real-time event forwarding
- ✅ Easy to test payment flows
- ✅ Works with test mode

**When to use Production Webhooks:**
- When deploying to production
- When you need to select specific events
- When you need a permanent endpoint
- When using live mode

## Quick Reference

```bash
# Install
brew install stripe/stripe-cli/stripe

# Login
stripe login

# Start forwarding (keep this running)
stripe listen --forward-to localhost:8000/api/billing/webhooks/stripe/

# Trigger test events
stripe trigger checkout.session.completed
stripe trigger setup_intent.succeeded

# View events in real-time
# (Events appear automatically in the terminal)
```

## What to Expect in Stripe Dashboard

### For Trial Subscriptions

When you create a subscription with a trial period:

**✅ You WILL see:**
- **Subscriptions section** → Subscription with status "Trialing"
  - Go to: Stripe Dashboard → Customers → [Your Customer] → Subscriptions
  - Or: Stripe Dashboard → Subscriptions (list all subscriptions)
  - Status: "Trialing" (orange badge)
  - Shows: Trial end date, subscription ID, price, etc.

**❌ You will NOT see:**
- **Transactions section** → No payment/charge yet
  - Transactions only appear when money is actually charged
  - For trials, Stripe only collects the payment method (no charge)
  - Transaction will appear when trial ends and first payment is charged

### Finding Your Subscription

1. **From Webhook Logs:**
   - Look for `customer.subscription.created` event
   - The subscription ID is in the event: `sub_xxxxx`
   - Example: `sub_1SmihpCIxQdkR5nZnLA0sPwI`

2. **In Stripe Dashboard:**
   - Go to: **Subscriptions** (left sidebar)
   - Search for the subscription ID
   - Or go to: **Customers** → Find your customer → View subscriptions

3. **Check Test Mode:**
   - Make sure you're in **Test Mode** (toggle in top right)
   - CLI only works with test mode subscriptions

### When Will Transaction Appear?

Transaction will appear in Stripe Dashboard when:
- ✅ Trial period ends (automatic charge)
- ✅ You manually charge the customer
- ✅ Subscription is upgraded/paid

**During trial:** Only payment method is collected, no charge = no transaction

### Verifying Subscription Details

In Stripe Dashboard, you should see:
- **Subscription ID**: `sub_xxxxx` (from webhook logs)
- **Status**: "Trialing"
- **Customer**: Your test customer
- **Price**: The subscription price
- **Trial End**: Date when trial ends
- **Metadata**: Course ID, class ID, etc. (if you added metadata)

## Next Steps

1. Keep `stripe listen` running in a terminal
2. Test your payment flow
3. Watch events arrive in real-time
4. Debug webhook handlers using Django logs
5. Check Stripe Dashboard → Subscriptions (not Transactions) for trial subscriptions
6. When ready for production, configure webhooks in Stripe Dashboard

