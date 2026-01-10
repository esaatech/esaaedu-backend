# Fix Plan: One-Time Trial Product Creation Issue

## Problem Analysis

### Current Code Structure

```
Line 1490-1510: Get billing_product (inside try/except)
  ├─ Success: billing_product = BillingProduct.objects.get(...)
  └─ Failure: billing_product is undefined

Line 1515: Branch on pricing_type
  ├─ pricing_type == 'monthly' (Line 1516)
  │   └─ Uses ensure_stripe_product_and_prices_in_current_environment() ✅ WORKS
  │
  └─ pricing_type == 'one_time' (Line 1918)
      ├─ has_trial_one_time == True (Line 1928)
      │   └─ Creates price with product_data ❌ CREATES NEW PRODUCT
      │
      └─ has_trial_one_time == False (Line 2234)
          └─ Uses PaymentIntent.create() ✅ WORKS (no product needed)
```

### Why It Breaks

**Line 1935-1946:** When creating price for one-time trial:
- `billing_product` is not accessible (out of scope from line 1491)
- Code uses `product_data={'name': ...}` which creates a NEW product
- Should use `product=existing_product_id` instead

### What Works (Don't Touch)

1. ✅ **Monthly subscriptions** (line 1516-1916)
   - Uses `ensure_stripe_product_and_prices_in_current_environment()`
   - Handles product creation/migration correctly
   - **DO NOT MODIFY**

2. ✅ **One-time without trial** (line 2234-2248)
   - Uses `PaymentIntent.create()`
   - No product needed (PaymentIntent doesn't require product)
   - **DO NOT MODIFY**

## Safe Fix Strategy

### Step 1: Make billing_product accessible
- Initialize `billing_product = None` before try/except block
- Set it in both success and failure cases (or keep None if doesn't exist)

### Step 2: Fix one-time trial path only
- Check if `billing_product` exists
- If exists: Use `product=billing_product.stripe_product_id`
- If not exists: Ensure product exists first, then use it

### Step 3: Ensure no side effects
- Monthly path: Unchanged
- One-time without trial: Unchanged
- Only one-time with trial: Fixed

## Implementation Plan

```python
# BEFORE (Line 1489-1510)
# Get billing data for the course
try:
    billing_product = BillingProduct.objects.get(course=course)
    # ... pricing_options ...
except BillingProduct.DoesNotExist:
    # ... pricing_options ...
    # billing_product is undefined here

# AFTER (Safe fix)
# Get billing data for the course
billing_product = None  # Initialize to None
try:
    billing_product = BillingProduct.objects.get(course=course)
    # ... pricing_options ...
except BillingProduct.DoesNotExist:
    # ... pricing_options ...
    # billing_product remains None

# THEN in one-time trial path (Line 1928-1946)
if has_trial_one_time:
    # Ensure product exists first
    if not billing_product:
        # Use existing function to ensure product exists
        ensure_stripe_product_and_prices_in_current_environment(course, billing_period='one_time')
        billing_product = BillingProduct.objects.get(course=course)
    
    # Now use existing product ID
    stripe_price = stripe.Price.create(
        product=billing_product.stripe_product_id,  # ✅ Use existing product
        unit_amount=amount,
        currency='usd',
        recurring={'interval': 'month'},
        metadata={...}  # Remove product_data
    )
```

## Testing Checklist

After fix, verify:

- [ ] Monthly subscription WITHOUT trial: Still works
- [ ] Monthly subscription WITH trial: Still works  
- [ ] One-time payment WITHOUT trial: Still works
- [ ] One-time payment WITH trial: Uses existing product (no new product created)
- [ ] All existing subscriptions continue to work
- [ ] No database errors
- [ ] No Stripe API errors

## Risk Assessment

**Low Risk:**
- Only touches one-time trial path (line 1928-1946)
- Uses existing `ensure_stripe_product_and_prices_in_current_environment()` function
- Initializes variable to None (safe default)
- All other paths remain unchanged

**Potential Issues:**
- If `billing_product` doesn't exist and `ensure_stripe_product_and_prices_in_current_environment()` fails
- Solution: Add try/except around product creation, fallback to current behavior if needed

