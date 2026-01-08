# Billing System Flow

## Overview
This document describes the billing flow for Little Learners Tech platform using Stripe integration.

## ASCII Flow Diagrams

### 1. Teacher Course Creation Flow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Teacher       │    │   Django API    │    │   Stripe        │
│   Dashboard     │    │   (Backend)     │    │   (Products)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
    ┌────▼────┐              ┌───▼───┐               ┌───▼───┐
    │ Teacher │              │ Course│               │ Stripe│
    │ Creates │              │ Model │               │ API   │
    │ Course  │              │       │               │       │
    └────┬────┘              └───┬───┘               └───┬───┘
         │                       │                       │
         │ 1. POST /api/courses/ │                       │
         │    (Course Data)      │                       │
         ├──────────────────────►│                       │
         │                       │                       │
         │ 2. Create Course      │                       │
         │    in Database        │                       │
         │                       │                       │
         │ 3. Create Stripe      │                       │
         │    Product            │                       │
         │                       ├──────────────────────►│
         │                       │                       │
         │ 4. Stripe Product ID  │                       │
         │◄──────────────────────┼───────────────────────┤
         │                       │                       │
         │ 5. Create Monthly     │                       │
         │    Price              │                       │
         │                       ├──────────────────────►│
         │                       │                       │
         │ 6. Monthly Price ID   │                       │
         │◄──────────────────────┼───────────────────────┤
         │                       │                       │
         │ 7. Create One-time    │                       │
         │    Price              │                       │
         │                       ├──────────────────────►│
         │                       │                       │
         │ 8. One-time Price ID  │                       │
         │◄──────────────────────┼───────────────────────┤
         │                       │                       │
         │ 9. Save Billing       │                       │
         │    Products & Prices  │                       │
         │                       │                       │
         │ 10. Course Created    │                       │
         │     Successfully      │                       │
         │◄──────────────────────┤                       │
```

### 2. Student Purchase Flow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Django API    │    │   Stripe        │
│   (React/Web)   │    │   (Backend)     │    │   (Payment)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
    ┌────▼────┐              ┌───▼───┐               ┌───▼───┐
    │ User    │              │ Billing│               │ Stripe│
    │ Selects │              │ Models │               │ API   │
    │ Course  │              │       │               │       │
    └────┬────┘              └───┬───┘               └───┬───┘
         │                       │                       │
         │ 1. GET /api/courses/  │                       │
         ├──────────────────────►│                       │
         │                       │                       │
         │ 2. Course List        │                       │
         │◄──────────────────────┤                       │
         │                       │                       │
         │ 3. User Clicks        │                       │
         │    "Subscribe"        │                       │
         │                       │                       │
         │ 4. POST /api/billing/ │                       │
         │    courses/{id}/      │                       │
         │    checkout-session/  │                       │
         ├──────────────────────►│                       │
         │                       │                       │
         │                       │ 5. Create/Get         │
         │                       │    Stripe Customer     │
         │                       ├──────────────────────►│
         │                       │                       │
         │                       │ 6. Create Checkout    │
         │                       │    Session            │
         │                       ├──────────────────────►│
         │                       │                       │
         │                       │ 7. Session URL        │
         │                       │◄──────────────────────┤
         │                       │                       │
         │ 8. Checkout URL       │                       │
         │◄──────────────────────┤                       │
         │                       │                       │
         │ 9. Redirect to        │                       │
         │    Stripe Checkout    │                       │
         ├──────────────────────────────────────────────►│
         │                       │                       │
         │ 10. User Completes    │                       │
         │     Payment           │                       │
         │                       │                       │
         │ 11. Stripe Webhook    │                       │
         │     (Payment Success) │                       │
         │◄──────────────────────┼───────────────────────┤
         │                       │                       │
         │ 12. Update Database   │                       │
         │     (Subscription)    │                       │
         │                       │                       │
         │ 13. Redirect to       │                       │
         │     Success Page      │                       │
         │◄──────────────────────┤                       │
```

## Detailed Flow Steps

### Teacher Course Creation Flow

#### 1. Course Creation
- Teacher logs into dashboard
- Teacher fills out course form (title, description, content, etc.)
- Teacher sets pricing (monthly subscription price, one-time price)
- Frontend calls `POST /api/courses/` with course data

#### 2. Backend Processing
- Django creates Course record in database
- Backend automatically creates Stripe Product for the course
- Backend determines billing strategy based on course duration:
  - **≤ 4 weeks**: Only one-time price
  - **> 4 weeks**: One-time price + monthly subscription price
- Backend saves BillingProduct and BillingPrice records linked to Course

#### 3. Course Activation
- Course is marked as active and available for purchase
- Teacher can manage course content and pricing
- Course appears in public course listing

#### 4. Course Updates

Course updates can be performed through **API** or **Django Admin**, both trigger automatic Stripe synchronization:

**API Updates** (`PUT /api/courses/{id}/`):
- **Price Updates**: If `price` or `is_free` changes:
  - All existing Stripe prices are deactivated
  - New prices are created with updated amounts
  - Billing records are updated in database
- **Duration Updates**: If `duration_weeks` changes:
  - Billing strategy is recalculated based on new duration
  - If duration changes from ≤4 weeks to >4 weeks:
    - Monthly subscription price is automatically created
    - Both one-time and monthly payment options become available
  - If duration changes from >4 weeks to ≤4 weeks:
    - Monthly subscription price is removed
    - Only one-time payment option remains
  - All existing Stripe prices are deactivated and new ones are created
- **Combined Updates**: If both price and duration change, prices are recalculated for both billing strategies

**Django Admin Updates**:
- Same automatic synchronization as API updates
- `CourseAdmin.save_model()` detects changes to `price`, `is_free`, or `duration_weeks`
- Automatically calls `update_stripe_product_for_course()` when billing fields change
- Shows success/warning messages in admin interface
- Only updates if course already has a `BillingProduct` (new courses skip until product is created)





### Student Purchase Flow

#### 1. Course Discovery
- User browses available courses
- Frontend calls `GET /api/courses/` to fetch course list
- Each course shows pricing options (monthly/one-time)

#### 2. Checkout Initiation
- User selects a course and pricing type
- Frontend calls `POST /api/billing/courses/{course_id}/checkout-session/`
- Backend:
  - Validates course and pricing type
  - Creates/retrieves Stripe customer
  - Creates Stripe checkout session
  - Returns session URL

#### 3. Payment Processing
- User is redirected to Stripe Checkout
- User enters payment information
- Stripe processes payment
- User is redirected back to success/cancel URL

#### 4. Webhook Processing
- Stripe sends webhook to backend
- Backend updates subscription status
- User gains access to course content

#### 5. Subscription Management
- User can view subscriptions: `GET /api/billing/subscriptions/me/`
- User can cancel subscription: `POST /api/billing/subscriptions/{id}/cancel/`

## Data Models

```
BillingProduct ──┐
                 ├── BillingPrice (monthly/one_time)
                 └── Course

CustomerAccount ──┐
                  ├── User
                  └── Stripe Customer ID

Subscription ──┐
               ├── User
               ├── Course
               ├── Stripe Subscription ID
               └── Status (active/trialing/canceled)

Payment ──┐
          ├── User
          ├── Subscription
          └── Stripe Payment Intent ID
```

## API Endpoints

### Course Management (Teacher)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/courses/` | Create new course (auto-creates Stripe products) |
| PUT | `/api/courses/{id}/` | Update course, pricing, or duration (auto-updates Stripe products/prices) |
| DELETE | `/api/courses/{id}/` | Deactivate course |

**Note on Course Updates**: When updating a course via PUT:
- **Price changes**: Stripe prices are recalculated and updated
- **Duration changes**: Billing strategy is automatically updated:
  - If duration changes from ≤4 weeks to >4 weeks: Monthly subscription price is created
  - If duration changes from >4 weeks to ≤4 weeks: Monthly subscription price is removed
- **Both price and duration**: All prices are recalculated based on new values

### Billing (Student)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/billing/courses/{id}/checkout-session/` | Create checkout session |
| GET | `/api/billing/subscriptions/me/` | List user subscriptions |
| POST | `/api/billing/subscriptions/{id}/cancel/` | Cancel subscription |
| POST | `/api/billing/webhooks/stripe/` | Stripe webhook handler |

## Environment Variables

```bash
STRIPE_SECRET_KEY=YOUR_SECRET_KEY_HERE
STRIPE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY_HERE
STRIPE_WEBHOOK_SECRET=YOUR_WEBHOOK_SECRET_HERE
```

## Error Handling

- Invalid course ID → 404 Not Found
- Invalid pricing type → 400 Bad Request
- Stripe API errors → 400 Bad Request
- Authentication required → 401 Unauthorized
- Missing Stripe configuration → 500 Internal Server Error
