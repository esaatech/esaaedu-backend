┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Stripe        │    │   Stripe        │    │   Your          │
│   Dashboard     │    │   Dashboard     │    │   Application   │
│   (API Keys)    │    │   (Webhooks)    │    │   (Backend)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │ 1. Get Secret Key     │                       │
         │    sk_test_...        │                       │
         ├──────────────────────►│                       │
         │                       │                       │
         │ 2. Get Publishable    │                       │
         │    pk_test_...        │                       │
         ├──────────────────────►│                       │
         │                       │                       │
         │ 3. Get Webhook Secret │                       │
         │    whsec_...          │                       │
         ├──────────────────────►│                       │
         │                       │                       │
         │ 4. Configure Keys     │                       │
         │    in .env            │                       │
         ├──────────────────────┼──────────────────────►│

         ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Stripe CLI    │    │   Local Django  │    │   Stripe        │
│   (Terminal)    │    │   Server        │    │   Dashboard     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │ 1. Install CLI        │                       │
         │    brew install       │                       │
         │    stripe/stripe-cli  │                       │
         │                       │                       │
         │ 2. Login to Stripe    │                       │
         │    stripe login       │                       │
         │                       │                       │
         │ 3. Start Forwarding   │                       │
         │    stripe listen      │                       │
         │    --forward-to       │                       │
         │    localhost:8000/    │                       │
         │    api/billing/       │                       │
         │    webhooks/stripe/   │                       │
         │                       │                       │
         │ 4. Get Webhook Secret │                       │
         │    whsec_...          │                       │
         │                       │                       │
         │ 5. Configure .env     │                       │
         │    STRIPE_SECRET_KEY  │                       │
         │    STRIPE_PUBLISHABLE │                       │
         │    STRIPE_WEBHOOK_    │                       │
         │    SECRET             │                       │
         │                       │                       │
         │ 6. Start Django       │                       │
         │    python manage.py   │                       │
         │    runserver 8000     │                       │
         │                       │                       │
         │ 7. Test Webhook       │                       │
         │    stripe trigger     │                       │
         │    checkout.session.  │                       │
         │    completed          │                       │
         │                       │                       │
         │ 8. Watch Events       │                       │
         │    All webhook events │                       │
         │    forwarded to       │                       │
         │    localhost:8000     │                       │
         │                       │                       │
         │ 9. Test Complete Flow │                       │
         │    Create course →    │                       │
         │    Call checkout →    │                       │
         │    Complete payment → │                       │
         │    Watch webhook      │                       │
         │    events             │                       │

         ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Stripe        │    │   Google Cloud  │    │   Your          │
│   Dashboard     │    │   Secret        │    │   Cloud Run     │
│   (Webhooks)    │    │   Manager       │    │   Service       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │ 1. Create Webhook     │                       │
         │    Endpoint URL:      │                       │
         │    https://esaaedu-   │                       │
         │    backend-578103433  │                       │
         │    472.us-central1.   │                       │
         │    run.app/api/       │                       │
         │    billing/webhooks/  │                       │
         │    stripe/            │                       │
         │                       │                       │
         │ 2. Select Events      │                       │
         │    checkout.session.  │                       │
         │    completed          │                       │
         │    customer.subscription.                     │
         │    created            │                       │
         │    customer.subscription.                     │
         │    updated            │                       │
         │    customer.subscription.                     │
         │    deleted            │                       │
         │    invoice.payment.   │                       │
         │    succeeded          │                       │
         │    invoice.payment.   │                       │
         │    failed             │                       │
         │                       │                       │
         │ 3. Get Webhook Secret │                       │
         │    whsec_...          │                       │
         │                       │                       │
         │ 4. Store in Secret    │                       │
         │    Manager            │                       │
         │                       ├──────────────────────►│
         │                       │                       │
         │ 5. Deploy to Cloud    │                       │
         │    Run                │                       │
         │                       ├──────────────────────►│
         │                       │                       │
         │ 6. Test Production    │                       │
         │    Webhook            │                       │
         │                       │                       │
         │ 7. Monitor Events     │                       │
         │    in Stripe          │                       │
         │    Dashboard          │                       │
         │                       │                       │
         │ 8. Verify Subscriptions                       │
         │    in Database        │                       │
         │                       │                       │
         │ 9. Production Ready   │                       │
         │    Live webhook       │                       │
         │    handling           │                       │