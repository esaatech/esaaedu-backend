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
- Backend creates two Stripe Prices:
  - Monthly recurring price (subscription)
  - One-time price (payment)
- Backend saves BillingProduct and BillingPrice records linked to Course

#### 3. Course Activation
- Course is marked as active and available for purchase
- Teacher can manage course content and pricing
- Course appears in public course listing





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
| PUT | `/api/courses/{id}/` | Update course and pricing |
| DELETE | `/api/courses/{id}/` | Deactivate course |

### Billing (Student)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/billing/courses/{id}/checkout-session/` | Create checkout session |
| GET | `/api/billing/subscriptions/me/` | List user subscriptions |
| POST | `/api/billing/subscriptions/{id}/cancel/` | Cancel subscription |
| POST | `/api/billing/webhooks/stripe/` | Stripe webhook handler |

## Environment Variables

```bash
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

## Error Handling

- Invalid course ID → 404 Not Found
- Invalid pricing type → 400 Bad Request
- Stripe API errors → 400 Bad Request
- Authentication required → 401 Unauthorized
- Missing Stripe configuration → 500 Internal Server Error
