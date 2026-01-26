"""
Utility functions for student enrollment operations
"""
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError


def complete_enrollment_without_stripe(
    student_profile,
    course,
    class_id,
    enrolled_by,
    payment_status='free',
    amount_paid=0,
    payment_due_date=None,
    create_payment_record=False
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
        create_payment_record: If True, creates a Payment record for cash payments
    
    Returns:
        EnrolledCourse instance if successful, None if error
    
    Raises:
        ValidationError: If class doesn't belong to course or other validation fails
    """
    from student.models import EnrolledCourse
    from courses.models import Class
    
    print(f"🎓 ENROLLMENT WITHOUT STRIPE: {student_profile.user.email} → {course.title} (Status: {payment_status}, Amount: {amount_paid})")
    
    with transaction.atomic():
        # Get student user
        user = student_profile.user
        
        # Check if enrollment already exists
        existing_enrollment = EnrolledCourse.objects.filter(
            student_profile=student_profile,
            course=course
        ).first()
        
        if existing_enrollment and existing_enrollment.status in ['active', 'completed']:
            print(f"✅ Enrollment already exists and is active: {existing_enrollment.id}")
            return existing_enrollment
        
        # Get the selected class if class_id is provided
        selected_class = None
        if class_id:
            try:
                selected_class = Class.objects.get(id=class_id, course=course, is_active=True)
            except Class.DoesNotExist:
                print(f"❌ Class {class_id} not found or doesn't belong to course {course.id}")
                raise ValidationError(f"Class {class_id} not found or doesn't belong to course {course.title}")
        
        # If enrollment exists but is inactive, reactivate it
        if existing_enrollment and existing_enrollment.status not in ['active', 'completed']:
            existing_enrollment.status = 'active'
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
                    if user not in selected_class.students.all() and selected_class.student_count < selected_class.max_capacity:
                        selected_class.students.add(user)
                        print(f"✅ Added student to class: {selected_class.name}")
                except Exception as e:
                    print(f"⚠️ Failed to add student to class: {e}")
            
            return existing_enrollment
        
        # Create new enrollment
        enrollment = EnrolledCourse.objects.create(
            student_profile=student_profile,
            course=course,
            status='active',
            enrolled_by=enrolled_by,
            
            # Payment information
            payment_status=payment_status,
            amount_paid=amount_paid,
            payment_due_date=payment_due_date,
            discount_applied=0,
            
            # Course initialization
            total_lessons_count=course.total_lessons or 0,
            total_assignments_assigned=getattr(course, 'total_assignments', 0),
            
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
        
        # Optionally create Payment record for cash payments (Phase 4)
        if create_payment_record and payment_status == 'paid' and amount_paid > 0:
            try:
                from billings.models import Payment
                Payment.objects.create(
                    user=user,
                    course=course,
                    amount=amount_paid,
                    currency='usd',
                    status='succeeded',
                    paid_at=timezone.now(),
                    # Leave Stripe fields blank for cash payments
                    stripe_payment_intent_id='',
                    stripe_invoice_id='',
                    stripe_charge_id=''
                )
                print(f"✅ Payment record created for cash payment: ${amount_paid}")
            except Exception as e:
                print(f"⚠️ Failed to create payment record: {e}")
                # Don't fail enrollment if payment record creation fails
        
        print(f"✅ Enrollment created: {enrollment.id}")
        return enrollment

