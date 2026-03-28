"""
Utility functions for student enrollment operations
"""
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.utils import timezone


def _payment_is_manual_cash(payment) -> bool:
    """True if this row is an admin/cash payment (no Stripe IDs)."""
    return (
        not (payment.stripe_payment_intent_id or "").strip()
        and not (payment.stripe_invoice_id or "").strip()
        and not (payment.stripe_charge_id or "").strip()
    )


def sync_manual_payment_from_enrollment(enrollment):
    """
    Mirror EnrolledCourse paid state to billings.Payment for manual/cash rows.

    - Links via Payment.enrolled_course (one manual Payment per enrollment).
    - Sets paid_at only when creating a new row or adopting an orphan.
    - Does not modify Stripe-backed Payment rows.
    """
    from billings.models import Payment

    user = enrollment.student_profile.user
    course = enrollment.course

    paid_ok = (
        enrollment.payment_status == "paid"
        and enrollment.amount_paid is not None
        and enrollment.amount_paid > Decimal("0")
    )

    try:
        payment = enrollment.manual_billing_payment
    except ObjectDoesNotExist:
        payment = None

    if not paid_ok:
        if payment and _payment_is_manual_cash(payment):
            if payment.status == Payment.STATUS_SUCCEEDED:
                payment.status = Payment.STATUS_CANCELED
                payment.save(update_fields=["status"])
        return payment

    if payment is not None:
        if not _payment_is_manual_cash(payment):
            return payment
        payment.user = user
        payment.course = course
        payment.amount = enrollment.amount_paid
        if payment.status != Payment.STATUS_SUCCEEDED:
            payment.status = Payment.STATUS_SUCCEEDED
        payment.save(update_fields=["user", "course", "amount", "status"])
        return payment

    orphan = (
        Payment.objects.filter(
            user=user,
            course=course,
            enrolled_course__isnull=True,
            stripe_payment_intent_id="",
            stripe_invoice_id="",
            stripe_charge_id="",
        )
        .order_by("-paid_at", "-created_at")
        .first()
    )
    if orphan:
        orphan.enrolled_course = enrollment
        orphan.amount = enrollment.amount_paid
        orphan.user = user
        orphan.course = course
        orphan.status = Payment.STATUS_SUCCEEDED
        if orphan.paid_at is None:
            orphan.paid_at = timezone.now()
        orphan.save(
            update_fields=[
                "enrolled_course",
                "amount",
                "user",
                "course",
                "status",
                "paid_at",
            ]
        )
        return orphan

    return Payment.objects.create(
        user=user,
        course=course,
        enrolled_course=enrollment,
        amount=enrollment.amount_paid,
        currency="usd",
        status=Payment.STATUS_SUCCEEDED,
        paid_at=timezone.now(),
        stripe_payment_intent_id="",
        stripe_invoice_id="",
        stripe_charge_id="",
    )


def complete_enrollment_without_stripe(
    student_profile,
    course,
    class_id,
    enrolled_by,
    payment_status="free",
    amount_paid=0,
    payment_due_date=None,
    create_payment_record=False,
):
    """
    Complete enrollment process without Stripe (for free courses, admin cash payments, scholarships).

    This function mirrors the logic of complete_enrollment_process() but:
    - Does not require or handle Stripe subscriptions
    - Accepts payment_status and amount_paid as parameters
    - Can optionally create a Payment record for audit trail

    Args:
        student_profile: StudentProfile instance
        course: Course instance
        class_id: UUID of the Class instance (can be None)
        enrolled_by: User instance (admin or student themselves)
        payment_status: Payment status ('free', 'paid', 'scholarship', etc.)
        amount_paid: Decimal amount paid (default 0)
        payment_due_date: Optional date when payment is due
        create_payment_record: Kept for callers; billing sync always runs after create/reactivate
            (creates/updates/cancels manual Payment from enrollment payment fields).

    Returns:
        EnrolledCourse instance if successful, None if error

    Raises:
        ValidationError: If class doesn't belong to course or other validation fails
    """
    from student.models import EnrolledCourse
    from courses.models import Class

    print(
        f"🎓 ENROLLMENT WITHOUT STRIPE: {student_profile.user.email} → {course.title} "
        f"(Status: {payment_status}, Amount: {amount_paid})"
    )

    with transaction.atomic():
        # Get student user
        user = student_profile.user

        # Check if enrollment already exists
        existing_enrollment = EnrolledCourse.objects.filter(
            student_profile=student_profile,
            course=course,
        ).first()

        if existing_enrollment and existing_enrollment.status in ["active", "completed"]:
            print(f"✅ Enrollment already exists and is active: {existing_enrollment.id}")
            return existing_enrollment

        # Get the selected class if class_id is provided
        selected_class = None
        if class_id:
            try:
                selected_class = Class.objects.get(id=class_id, course=course, is_active=True)
            except Class.DoesNotExist:
                print(f"❌ Class {class_id} not found or doesn't belong to course {course.id}")
                raise ValidationError(
                    f"Class {class_id} not found or doesn't belong to course {course.title}"
                )

        # If enrollment exists but is inactive, reactivate it
        if existing_enrollment and existing_enrollment.status not in ["active", "completed"]:
            existing_enrollment.status = "active"
            existing_enrollment.payment_status = payment_status
            existing_enrollment.amount_paid = amount_paid
            if payment_due_date:
                existing_enrollment.payment_due_date = payment_due_date
            existing_enrollment.enrolled_by = enrolled_by
            existing_enrollment.save()
            print(f"✅ Reactivated existing enrollment: {existing_enrollment.id}")

            # Add student to class if not already added
            if selected_class:
                try:
                    if (
                        user not in selected_class.students.all()
                        and selected_class.student_count < selected_class.max_capacity
                    ):
                        selected_class.students.add(user)
                        print(f"✅ Added student to class: {selected_class.name}")
                except Exception as e:
                    print(f"⚠️ Failed to add student to class: {e}")

            try:
                sync_manual_payment_from_enrollment(existing_enrollment)
            except Exception as e:
                print(f"⚠️ Failed to sync payment record: {e}")

            return existing_enrollment

        # Create new enrollment
        enrollment = EnrolledCourse.objects.create(
            student_profile=student_profile,
            course=course,
            status="active",
            enrolled_by=enrolled_by,
            # Payment information
            payment_status=payment_status,
            amount_paid=amount_paid,
            payment_due_date=payment_due_date,
            discount_applied=0,
            # Course initialization
            total_lessons_count=course.total_lessons or 0,
            total_assignments_assigned=getattr(course, "total_assignments", 0),
            # Progress tracking initialization
            progress_percentage=0,
            completed_lessons_count=0,
            total_assignments_completed=0,
            # Engagement defaults
            total_study_time=timezone.timedelta(),
            total_video_watch_time=timezone.timedelta(),
            login_count=0,
            # Communication preferences
            parent_notifications_enabled=True,
            reminder_emails_enabled=True,
        )

        # Add student to the selected class
        if selected_class:
            try:
                if selected_class.student_count < selected_class.max_capacity:
                    selected_class.students.add(user)
                    print(f"✅ Added student to class: {selected_class.name}")
                else:
                    print(f"⚠️ Class {selected_class.name} is at maximum capacity, student not added")
            except Exception as e:
                print(f"⚠️ Failed to add student to class: {e}")

        try:
            sync_manual_payment_from_enrollment(enrollment)
        except Exception as e:
            print(f"⚠️ Failed to sync payment record: {e}")

        print(f"✅ Enrollment created: {enrollment.id}")
        return enrollment
