# Staff payments list API

Canonical **read** surface for payment ledger rows (`billings.Payment`). Use this URL for scripts and future agent tools; the orchestrator is not implemented here—only the backend contract.

## Endpoint

- **Method / URL:** `GET /api/billing/payments/`
- **Name:** `billing:billing-payment-list` (Django `reverse`)
- **Auth:** Same as other API routes (Firebase per `REST_FRAMEWORK`). Permission is **`IsAuthenticated` + `IsAdminUser`** (Django: `user.is_staff` must be true).

## Query parameters (filters)

| Parameter | Type | Description |
|-----------|------|-------------|
| `page` | integer | Page number (default pagination). |
| `page_size` | integer | Optional; max `100`. |
| `status` | string | Exact match on `Payment.status`. |
| `user_id` | integer | Filter by payer user pk. |
| `course_id` | UUID | Filter by course pk. |
| `enrolled_course_id` | integer | Filter by linked `EnrolledCourse` pk when set. |
| `paid_after` | ISO date or datetime | Inclusive lower bound on `paid_at` (aware in server TZ). |
| `paid_before` | ISO date or datetime | Inclusive upper bound on `paid_at`. |

Invalid filter values return **400** with `{"detail": "..."}`.

## Response shape

Paginated list (project default `PAGE_SIZE` 20 unless overridden):

```json
{
  "count": 0,
  "next": null,
  "previous": null,
  "results": []
}
```

Each element of `results` matches **`PaymentListSerializer`** and the JSON Schemas in this repo:

- [`billings/schemas/payment_list_item.schema.json`](../schemas/payment_list_item.schema.json)
- [`billings/schemas/payment_list_page.schema.json`](../schemas/payment_list_page.schema.json)

`amount` is serialized as a **decimal string** (DRF default). `is_manual` is `true` when all of `stripe_payment_intent_id`, `stripe_invoice_id`, and `stripe_charge_id` are empty (admin / non-Stripe cash rows).

## Implementation map (single code path)

- **Queryset / filters:** `billings.services.payments.get_staff_payments_queryset`
- **HTTP view:** `billings.staff_payments.StaffPaymentListView`
- **JSON fields:** `billings.serializers.PaymentListSerializer`

Agent tools should call this endpoint (or import the service + serializer in-process) and must not reimplement ad-hoc queries.

## Example

```http
GET /api/billing/payments/?status=succeeded&page=1
Authorization: Bearer <token>
```
