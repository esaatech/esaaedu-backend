# Course Creation Architecture

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           COURSE CREATION SYSTEM                                │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Django API    │    │  Stripe Utils   │    │   External      │
│   (Teacher UI)  │    │   (courses/)    │    │ (stripe_integration.py) │   Services      │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │
         │ HTTP Request          │                       │                       │
         ├──────────────────────►│                       │                       │
         │                       │                       │                       │
         │                       │ Direct Function Call  │                       │
         │                       ├──────────────────────►│                       │
         │                       │                       │                       │
         │                       │                       │ Stripe API Calls      │
         │                       │                       ├──────────────────────►│
         │                       │                       │                       │
         │                       │                       │ Database Operations   │
         │                       │                       ├──────────────────────►│
         │                       │                       │                       │
         │ HTTP Response         │                       │                       │
         │◄──────────────────────┤                       │                       │
```

## File Structure

```
courses/
├── views.py                    # Course creation endpoint
├── stripe_integration.py       # Stripe utility functions
├── docs/
│   ├── course_creation_flow.md # Detailed flow documentation
│   └── architecture_diagram.md # This file
└── ...

billings/
├── models.py                   # BillingProduct, BillingPrice models
├── views.py                    # Billing API endpoints
└── ...
```

## Data Flow

1. **Teacher** creates course via frontend
2. **Django API** (`courses/views.py`) receives request
3. **Stripe Utils** (`courses/stripe_integration.py`) handles billing
4. **External Services** (Stripe API) creates products/prices
5. **Database** stores billing information
6. **Response** sent back to frontend

## Key Components

### `courses/views.py`
- `teacher_courses()` - Main course creation endpoint
- Handles POST requests for course creation
- Calls Stripe utility functions
- Returns course data with billing info

### `courses/stripe_integration.py`
- `create_stripe_product_for_course()` - Creates Stripe products
- `update_stripe_product_for_course()` - Updates Stripe products
- `deactivate_stripe_product_for_course()` - Deactivates Stripe products
- Direct database operations on billing models

### `billings/models.py`
- `BillingProduct` - Stores Stripe product information
- `BillingPrice` - Stores Stripe price information
- Linked to Course model

## Integration Points

- **No HTTP calls** between courses and billings apps
- **Direct model access** from stripe_integration.py
- **Stripe API calls** for external product/price creation
- **Database transactions** for data consistency
