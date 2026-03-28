# Admin / manual enrollment → `billing.Payment` sync

This note explains how **`EnrolledCourse`** financial fields stay aligned with **`billings.Payment`**, so the Django admin dashboard (“Paid today / week / month”) and billing reports see manual (non-Stripe) payments.

## Why it exists

- The admin dashboard (`users/templatetags/admin_dashboard.py`) aggregates **succeeded** `Payment` rows by **`paid_at`** (calendar timezone aware).
- **`EnrolledCourse`** stores **`payment_status`**, **`amount_paid`**, **`payment_due_date`** separately. Editing those in admin used to **not** create or update `Payment`, so the dashboard missed staff-entered payments.

## Data model

- **`Payment.enrolled_course`** — optional **`OneToOneField`** to **`student.EnrolledCourse`** (`related_name='manual_billing_payment'`).
- At most **one** manual billing row per enrollment for this link.
- Stripe-backed payments should keep Stripe IDs set and typically leave **`enrolled_course`** null; sync logic **does not** modify rows that have Stripe IDs (not “manual cash”).

**Migration:** `billings/migrations/0006_payment_enrolled_course.py` (depends on `billings.0005` and latest `student` migration at time of add).

## Sync entry point

**Function:** `sync_manual_payment_from_enrollment(enrollment)` in **`student/utils.py`**.

Behavior:

1. **Paid + `amount_paid` > 0**  
   - If a linked **`manual_billing_payment`** exists and is manual (empty Stripe IDs): **update** amount, user, course, status → **succeeded**.  
   - Else try to **adopt** an **orphan** manual `Payment` (same user + course, `enrolled_course` null, empty Stripe IDs), set **`enrolled_course`**, fix amount/status, set **`paid_at`** if it was null.  
   - Else **create** a new `Payment` with **`enrolled_course`**, **`paid_at=now`**, status **succeeded**, empty Stripe IDs.

2. **Not paid or amount ≤ 0**  
   - If linked payment exists and is **manual** and **succeeded**: set status to **`canceled`** (drops out of succeeded totals on the dashboard).

**`paid_at`** is **not** reset on every save when updating an existing linked row (only set on create / adopt when missing), so week/month buckets stay stable when staff only tweak amount.

## Where sync runs

| Trigger | Location |
|--------|----------|
| New enrollment or reactivation via **`complete_enrollment_without_stripe`** | **`student/utils.py`** — after create/reactivate |
| **Edit** existing enrollment in Django admin | **`student/admin.py`** — `EnrolledCourseAdmin.save_model` after `super().save_model` |

Failures on edit show an admin **warning** and are logged; the enrollment save still succeeds.

## Troubleshooting

| Symptom | Things to check |
|--------|------------------|
| Dashboard “Paid this week” missing after marking Paid in admin | Run **`migrate`** for `billings`. Confirm **`payment_status=paid`** and **`amount_paid` > 0**. Re-save the enrollment. |
| Duplicate amounts | Old rows may exist **without** `enrolled_course`; adoption links one orphan. If two orphans exist, inspect **`billing_payments`** for same user/course + empty Stripe fields. |
| Stripe payment changed unexpectedly | Sync **ignores** rows with Stripe IDs; if that happens, investigate other code paths, not `sync_manual_payment_from_enrollment`. |
| Canceled payment after clearing Paid | Expected: manual succeeded row is **canceled** when enrollment is no longer paid / amount zero. |

## Admin UI

- **Billing → Payments** list includes **`enrolled_course`** (`billings/admin.py`) for quick cross-check.

## Related docs

- **[student/docs/ADMIN_ENROLLMENT.md](../../student/docs/ADMIN_ENROLLMENT.md)** — admin enrollment flow and payment fields.
