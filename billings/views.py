from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import HttpResponse
from django.db import transaction
import os
import stripe
import json

from .models import BillingProduct, BillingPrice, CustomerAccount, Payment, WebhookEvent, Subscribers
from courses.models import Course
from student.models import EnrolledCourse
from settings.models import CourseSettings


def get_stripe_client() -> None:
    api_key = os.environ.get('STRIPE_SECRET_KEY') or getattr(settings, 'STRIPE_SECRET_KEY', None)
    if not api_key:
        raise RuntimeError("Stripe secret key not configured (STRIPE_SECRET_KEY)")
    stripe.api_key = api_key


def get_trial_period_settings():
    """Get trial period settings from CourseSettings"""
    try:
        settings = CourseSettings.get_settings()
        return {
            'enabled': settings.enable_trial_period,
            'days': settings.trial_period_days
        }
    except Exception as e:
        # Fallback to default values
        return {
            'enabled': True,
            'days': 14
        }


def ensure_stripe_customer_in_current_environment(user):
    """
    Ensure Stripe customer exists in the current environment (test/live).
    If customer ID is from wrong environment, create new customer and update database.
    
    Args:
        user: User model instance
        
    Returns:
        str: The valid customer ID for the current environment
    """
    try:
        # Get or create customer account
        customer_account, created = CustomerAccount.objects.get_or_create(
            user=user,
            defaults={'stripe_customer_id': ''}
        )
        
        # If no customer ID exists, create one
        if not customer_account.stripe_customer_id:
            print(f"🔄 Creating new Stripe customer for user: {user.email}")
            stripe_customer = stripe.Customer.create(
                email=user.email,
                name=f"{user.first_name} {user.last_name}".strip() or user.email,
                metadata={
                    'user_id': str(user.id),
                }
            )
            customer_account.stripe_customer_id = stripe_customer.id
            customer_account.save(update_fields=['stripe_customer_id'])
            print(f"✅ Created new customer {stripe_customer.id} and updated database")
            return stripe_customer.id
        
        # Check if customer exists in current environment
        try:
            stripe.Customer.retrieve(customer_account.stripe_customer_id)
            print(f"✅ Customer {customer_account.stripe_customer_id} exists in current environment")
            return customer_account.stripe_customer_id
        except stripe.error.InvalidRequestError as e:
            error_message = str(e)
            error_code = getattr(e, 'code', '')
            
            if 'No such customer' in error_message or error_code == 'resource_missing':
                print(f"⚠️ Customer {customer_account.stripe_customer_id} not found in current environment - will migrate")
                # Create new customer in current environment
                print(f"🔄 Creating new Stripe customer in current environment for user: {user.email}")
                stripe_customer = stripe.Customer.create(
                    email=user.email,
                    name=f"{user.first_name} {user.last_name}".strip() or user.email,
                    metadata={
                        'user_id': str(user.id),
                        'migrated_from': customer_account.stripe_customer_id  # Track migration
                    }
                )
                old_customer_id = customer_account.stripe_customer_id
                customer_account.stripe_customer_id = stripe_customer.id
                customer_account.save(update_fields=['stripe_customer_id'])
                print(f"✅ Created new customer {stripe_customer.id} and updated database (migrated from {old_customer_id})")
                return stripe_customer.id
            else:
                # Different error, re-raise it
                raise e
                
    except Exception as e:
        print(f"❌ Error ensuring Stripe customer in current environment: {e}")
        import traceback
        traceback.print_exc()
        raise e


def ensure_stripe_product_and_prices_in_current_environment(course, billing_period='monthly'):
    """
    Ensure Stripe product and prices exist in the current environment (test/live).
    If they're from the wrong environment, migrate them by creating new ones.
    
    This function:
    1. Checks if the Stripe Product exists in current environment
    2. If not, creates a new Product and updates BillingProduct
    3. Checks if the requested Price exists in current environment
    4. If not, creates new Prices and updates BillingPrice records
    
    Args:
        course: Course model instance
        billing_period: 'monthly' or 'one_time' - which price to return
        
    Returns:
        str: The valid price ID for the current environment
    """
    from courses.price_calculator import calculate_course_prices
    
    try:
        # Get or create billing product
        billing_product, created = BillingProduct.objects.get_or_create(
            course=course,
            defaults={'stripe_product_id': '', 'is_active': True}
        )
        
        # Step 1: Check if Product exists in current environment
        product_exists = False
        stripe_product_id = billing_product.stripe_product_id
        
        if stripe_product_id:
            try:
                stripe.Product.retrieve(stripe_product_id)
                product_exists = True
                print(f"✅ Product {stripe_product_id} exists in current environment")
            except stripe.error.InvalidRequestError as e:
                if 'No such product' in str(e) or getattr(e, 'code', '') == 'resource_missing':
                    print(f"⚠️ Product {stripe_product_id} not found in current environment - will migrate")
                    product_exists = False
                else:
                    raise e
        
        # Step 2: Create new Product if it doesn't exist
        if not product_exists:
            print(f"🔄 Creating new Stripe Product in current environment for course: {course.title}")
            stripe_product = stripe.Product.create(
                name=course.title,
                description=course.description or course.long_description or '',
                metadata={
                    'course_id': str(course.id),
                    'teacher_id': str(course.teacher.id) if course.teacher else '',
                    'duration_weeks': str(course.duration_weeks) if course.duration_weeks else '0',
                }
            )
            stripe_product_id = stripe_product.id
            
            # Update database with new product ID
            billing_product.stripe_product_id = stripe_product_id
            billing_product.is_active = True
            billing_product.save(update_fields=['stripe_product_id', 'is_active'])
            print(f"✅ Created new product {stripe_product_id} and updated database")
        else:
            stripe_product_id = billing_product.stripe_product_id
        
        # Step 3: Calculate prices (same logic as course creation)
        prices = calculate_course_prices(float(course.price), course.duration_weeks or 0)
        
        # Step 4: Check and migrate prices
        # Get ALL existing prices from database (not just first)
        existing_prices = BillingPrice.objects.filter(
            product=billing_product,
            is_active=True
        )
        
        # Check all one-time prices to find one that exists in current environment
        one_time_price_id = None
        one_time_price_obj = None
        one_time_prices = existing_prices.filter(billing_period='one_time')
        
        for price_obj in one_time_prices:
            if price_obj.stripe_price_id:
                try:
                    stripe.Price.retrieve(price_obj.stripe_price_id)
                    # Found a valid price in current environment
                    one_time_price_id = price_obj.stripe_price_id
                    one_time_price_obj = price_obj
                    print(f"✅ Found valid one-time price {one_time_price_id} in current environment")
                    break
                except stripe.error.InvalidRequestError as e:
                    if 'No such price' in str(e) or getattr(e, 'code', '') == 'resource_missing':
                        # This price doesn't exist in current environment, mark as invalid
                        print(f"⚠️ One-time price {price_obj.stripe_price_id} not found in current environment - will deactivate")
                        price_obj.is_active = False
                        price_obj.save(update_fields=['is_active'])
                    else:
                        raise e
        
        # Only create new one-time price if no valid one exists
        if not one_time_price_id:
            print(f"🔄 No valid one-time price found - creating new one in current environment")
            new_one_time_price = stripe.Price.create(
                product=stripe_product_id,
                unit_amount=int(prices['one_time_price'] * 100),  # Convert to cents
                currency='usd',
                metadata={
                    'course_id': str(course.id),
                    'billing_type': 'one_time',
                    'migrated': 'true'  # Track that this was migrated
                }
            )
            one_time_price_id = new_one_time_price.id
            
            # Create new BillingPrice record (don't reuse old invalid ones)
            BillingPrice.objects.create(
                product=billing_product,
                stripe_price_id=one_time_price_id,
                billing_period='one_time',
                unit_amount=prices['one_time_price'],
                currency='usd',
                is_active=True
            )
            print(f"✅ Created new one-time price {one_time_price_id} and updated database")
        
        # Check and migrate monthly price (if course duration > 4 weeks)
        monthly_price_id = None
        monthly_price_obj = None
        
        if prices['total_months'] > 1:
            # Check all monthly prices to find one that exists in current environment
            monthly_prices = existing_prices.filter(billing_period='monthly')
            
            for price_obj in monthly_prices:
                if price_obj.stripe_price_id:
                    try:
                        stripe.Price.retrieve(price_obj.stripe_price_id)
                        # Found a valid price in current environment
                        monthly_price_id = price_obj.stripe_price_id
                        monthly_price_obj = price_obj
                        print(f"✅ Found valid monthly price {monthly_price_id} in current environment")
                        break
                    except stripe.error.InvalidRequestError as e:
                        if 'No such price' in str(e) or getattr(e, 'code', '') == 'resource_missing':
                            # This price doesn't exist in current environment, mark as invalid
                            print(f"⚠️ Monthly price {price_obj.stripe_price_id} not found in current environment - will deactivate")
                            price_obj.is_active = False
                            price_obj.save(update_fields=['is_active'])
                        else:
                            raise e
            
            # Only create new monthly price if no valid one exists
            if not monthly_price_id:
                print(f"🔄 No valid monthly price found - creating new one in current environment")
                new_monthly_price = stripe.Price.create(
                    product=stripe_product_id,
                    unit_amount=int(prices['monthly_price'] * 100),  # Convert to cents
                    currency='usd',
                    recurring={'interval': 'month'},
                    metadata={
                        'course_id': str(course.id),
                        'billing_type': 'monthly',
                        'total_months': str(prices['total_months']),
                        'monthly_total': str(prices['monthly_total']),
                        'migrated': 'true'  # Track that this was migrated
                    }
                )
                monthly_price_id = new_monthly_price.id
                
                # Create new BillingPrice record (don't reuse old invalid ones)
                BillingPrice.objects.create(
                    product=billing_product,
                    stripe_price_id=monthly_price_id,
                    billing_period='monthly',
                    unit_amount=prices['monthly_price'],
                    currency='usd',
                    is_active=True
                )
                print(f"✅ Created new monthly price {monthly_price_id} and updated database")
        
        # Return the requested price ID
        if billing_period == 'monthly':
            if not monthly_price_id:
                raise Exception(f"Monthly pricing not available for this course (duration: {course.duration_weeks} weeks)")
            return monthly_price_id
        else:  # one_time
            return one_time_price_id
            
    except Exception as e:
        print(f"❌ Error ensuring Stripe product/prices in current environment: {e}")
        import traceback
        traceback.print_exc()
        raise e


def update_subscription_type_from_stripe(subscription_id):
    """Update subscription type based on Stripe metadata when trial ends and payment is charged"""
    try:
        # Get Stripe subscription to read metadata
        stripe_subscription = stripe.Subscription.retrieve(subscription_id)
        pricing_type = stripe_subscription.metadata.get('pricing_type', 'monthly')
        
        # Update local subscriber record
        subscriber = Subscribers.objects.get(stripe_subscription_id=subscription_id)
        subscriber.subscription_type = pricing_type  # Update from 'trial' to 'monthly' or 'one_time'
        subscriber.status = 'active'  # Also update status to active when trial ends
        subscriber.save()
        
        print(f"✅ Updated subscriber {subscriber.id}: type=trial → {pricing_type}, status=trialing → active")
        return True
    except Exception as e:
        print(f"⚠️ Error updating subscription type: {e}")
        return False


def complete_enrollment_process(subscription_id, user, course, class_id, pricing_type, is_trial=False):
    """
    Complete enrollment process with row-level locking to prevent race conditions.
    This function is idempotent and can be called multiple times safely.
    """
    print(f"🎓 ENROLLMENT PROCESS: {user.email} → {course.title} (Trial: {is_trial})")
    
    from student.models import EnrolledCourse
    from courses.models import Class
    from datetime import timedelta
    
    with transaction.atomic():
        # Get subscription with row lock to prevent race conditions
        try:
            subscription = Subscribers.objects.select_for_update().get(
                stripe_subscription_id=subscription_id
            )
        except Subscribers.DoesNotExist:
            print(f"⚠️ Subscription {subscription_id} not found in local database")
            return None
        
        # Get student profile first
        student_profile = getattr(user, 'student_profile', None)
        if not student_profile:
            print(f"❌ Student profile not found for user {user.id}")
            return None
        
        # Check if enrollment already exists first (regardless of subscription status)
        existing_enrollment = EnrolledCourse.objects.filter(
            student_profile=student_profile,
            course=course
        ).first()
        
        if existing_enrollment and existing_enrollment.status in ['active', 'completed']:
                print(f"✅ Enrollment already exists and is active: {existing_enrollment.id}")
            # Update subscription status to match
                subscription.status = 'active' if not is_trial else 'trialing'
                subscription.save()
                return existing_enrollment
        
        # Get the selected class
        try:
            selected_class = Class.objects.get(id=class_id)
        except Class.DoesNotExist:
            print(f"❌ Class {class_id} not found")
            return None
        
        # If enrollment exists but is inactive, reactivate it
        if existing_enrollment and existing_enrollment.status not in ['active', 'completed']:
                existing_enrollment.status = 'active'
                existing_enrollment.save()
                print(f"✅ Reactivated existing enrollment: {existing_enrollment.id}")
                # Update subscription status
                subscription.status = 'active' if not is_trial else 'trialing'
                subscription.save()
                return existing_enrollment
        
        # Calculate payment details based on trial vs paid
        if is_trial:
            trial_settings = get_trial_period_settings()
            trial_days = trial_settings['days'] if trial_settings['enabled'] else 14
            trial_end_date = timezone.now().date() + timedelta(days=trial_days)
            payment_status = 'free'
            amount_paid = 0
            payment_due_date = trial_end_date
        else:
            # Paid enrollment - get actual pricing
            try:
                billing_product = BillingProduct.objects.get(course=course)
                if pricing_type == 'monthly':
                    monthly_price = BillingPrice.objects.filter(
                        product=billing_product, billing_period='monthly', is_active=True
                    ).first()
                    amount_paid = float(monthly_price.unit_amount) / 100 if monthly_price else float(course.price) * 1.15
                else:
                    one_time_price = BillingPrice.objects.filter(
                        product=billing_product, billing_period='one_time', is_active=True
                    ).first()
                    amount_paid = float(one_time_price.unit_amount) / 100 if one_time_price else float(course.price)
            except BillingProduct.DoesNotExist:
                amount_paid = float(course.price) * 1.15 if pricing_type == 'monthly' else float(course.price)
            
            payment_status = 'paid'
            payment_due_date = None
        
        # Create enrollment
        enrollment = EnrolledCourse.objects.create(
            student_profile=student_profile,
            course=course,
            status='active',
            enrolled_by=user,
            
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
        try:
            if selected_class.student_count < selected_class.max_capacity:
                selected_class.students.add(user)
        except Exception as e:
            print(f"⚠️ Failed to add student to class: {e}")
        
        # Update subscription status
        if is_trial:
            subscription.status = 'trialing'  # Update to trialing for trial enrollments
        else:
            subscription.status = 'active'    # Update to active for paid enrollments
        subscription.save()
        
        print(f"✅ Enrollment created: {enrollment.id}")
        return enrollment


class CreateCheckoutSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id: str):
        try:
            get_stripe_client()

            pricing_type = request.data.get('pricing_type', 'monthly')
            if pricing_type not in ('monthly', 'one_time'):
                return Response({"detail": "Invalid pricing_type"}, status=status.HTTP_400_BAD_REQUEST)

            course = get_object_or_404(Course, id=course_id)
            product = get_object_or_404(BillingProduct, course=course, is_active=True)
            price = get_object_or_404(
                BillingPrice,
                product=product,
                billing_period=pricing_type,
                is_active=True,
            )

            # Ensure Stripe Customer
            customer, _ = CustomerAccount.objects.get_or_create(
                user=request.user,
                defaults={'stripe_customer_id': ''},
            )
            if not customer.stripe_customer_id:
                created = stripe.Customer.create(email=request.user.email or None)
                customer.stripe_customer_id = created['id']
                customer.save(update_fields=['stripe_customer_id'])

            if pricing_type == 'monthly':
                # Get trial period settings
                trial_settings = get_trial_period_settings()
                trial_days = trial_settings['days'] if trial_settings['enabled'] else None
                
                # Subscription with trial period, card collected
                session = stripe.checkout.Session.create(
                    mode='subscription',
                    customer=customer.stripe_customer_id,
                    line_items=[{"price": price.stripe_price_id, "quantity": 1}],
                    subscription_data={"trial_period_days": trial_days},
                    allow_promotion_codes=True,
                    success_url=request.data.get('success_url') or 'https://example.com/success',
                    cancel_url=request.data.get('cancel_url') or 'https://example.com/cancel',
                )
            else:
                # One-time payment
                session = stripe.checkout.Session.create(
                    mode='payment',
                    customer=customer.stripe_customer_id,
                    line_items=[{"price": price.stripe_price_id, "quantity": 1}],
                    allow_promotion_codes=True,
                    success_url=request.data.get('success_url') or 'https://example.com/success',
                    cancel_url=request.data.get('cancel_url') or 'https://example.com/cancel',
                )

            return Response({"id": session['id'], "url": session['url']}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ListMySubscriptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get only active and trialing subscriptions
        subs = Subscribers.objects.filter(
            user=request.user,
            status__in=['active', 'trialing']
        ).values(
            'id', 'course_id', 'stripe_subscription_id', 'stripe_price_id', 'status',
            'subscription_type', 'current_period_start', 'current_period_end', 'cancel_at',
            'next_invoice_date', 'next_invoice_amount', 'trial_end', 'billing_interval', 'amount'
        )
        # Convert datetimes to ISO and add display information
        data = []
        for s in subs:
            # Calculate display information
            is_trial = s['status'] == 'trialing'
            is_monthly = s['subscription_type'] == 'monthly'
            is_one_time = s['subscription_type'] == 'one_time'
            
            # Determine payment description - focus on next invoice, not payment type
            if is_trial:
                # For trials, show when trial ends and what happens next
                if s['next_invoice_date'] and s['next_invoice_amount']:
                    payment_description = f"Next invoice: ${float(s['next_invoice_amount']):.2f} on {s['next_invoice_date'].strftime('%b %d, %Y')}"
                else:
                    trial_end = s['trial_end'].strftime('%b %d, %Y') if s['trial_end'] else 'N/A'
                    payment_description = f"Trial ends {trial_end}"
            elif is_monthly:
                # For monthly, show next invoice
                # Use current_period_end as fallback if next_invoice_date is not set
                next_billing_date = s.get('next_invoice_date')
                if not next_billing_date and s.get('current_period_end'):
                    next_billing_date = s['current_period_end']
                
                if next_billing_date and s.get('next_invoice_amount'):
                    payment_description = f"Next invoice: ${float(s['next_invoice_amount']):.2f} on {next_billing_date.strftime('%b %d, %Y')}"
                elif next_billing_date:
                    amount = float(s['amount']) if s.get('amount') else 0
                    payment_description = f"Next invoice: ${amount:.2f} on {next_billing_date.strftime('%b %d, %Y')}" if amount > 0 else f"Next billing: {next_billing_date.strftime('%b %d, %Y')}"
                else:
                    amount = float(s['amount']) if s.get('amount') else 0
                    payment_description = f"Monthly installments of ${amount:.2f}" if amount > 0 else "Monthly installments"
            else:  # one_time
                # For one-time, show the total amount
                amount = float(s['amount']) if s['amount'] else 0
                payment_description = f"Total amount: ${amount:.2f}" if amount > 0 else "One-time payment"
            
            # Next invoice information
            # Use current_period_end as fallback if next_invoice_date is not set
            next_billing_date = s.get('next_invoice_date')
            if not next_billing_date and s.get('current_period_end'):
                next_billing_date = s['current_period_end']
            
            next_invoice_info = None
            if next_billing_date:
                amount = float(s.get('next_invoice_amount', 0)) if s.get('next_invoice_amount') else (float(s.get('amount', 0)) if s.get('amount') else 0)
                next_invoice_info = {
                    'date': next_billing_date.strftime('%b %d, %Y'),
                    'amount': amount,
                    'formatted': f"${amount:.2f} on {next_billing_date.strftime('%b %d, %Y')}" if amount > 0 else f"Next billing: {next_billing_date.strftime('%b %d, %Y')}"
                }
            
            data.append({
                **s,
                'current_period_start': s['current_period_start'].isoformat() if s['current_period_start'] else None,
                'current_period_end': s['current_period_end'].isoformat() if s['current_period_end'] else None,
                'cancel_at': s['cancel_at'].isoformat() if s['cancel_at'] else None,
                'next_invoice_date': s['next_invoice_date'].isoformat() if s['next_invoice_date'] else None,
                'trial_end': s['trial_end'].isoformat() if s['trial_end'] else None,
                'amount': float(s['amount']) if s['amount'] else 0,
                'next_invoice_amount': float(s['next_invoice_amount']) if s['next_invoice_amount'] else 0,
                'payment_description': payment_description,
                'is_trial': is_trial,
                'is_monthly': is_monthly,
                'is_one_time': is_one_time,
                'next_invoice_info': next_invoice_info,
                'trial_end_formatted': s['trial_end'].strftime('%b %d, %Y') if s['trial_end'] else None,
            })
        return Response(data)


class CancelSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, subscription_id: str):
        try:
            get_stripe_client()
            sub = get_object_or_404(Subscribers, id=subscription_id, user=request.user)
            # Set cancel at period end in Stripe
            updated = stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=True)
            # Mirror locally
            cancel_at_ts = updated.get('cancel_at')
            if cancel_at_ts:
                sub.cancel_at = timezone.datetime.fromtimestamp(cancel_at_ts, tz=timezone.utc)
            sub.status = updated.get('status', sub.status)
            sub.save(update_fields=['cancel_at', 'status', 'updated_at'])
            return Response({"status": sub.status, "cancel_at": sub.cancel_at.isoformat() if sub.cancel_at else None})
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    
    """
    Handle Stripe webhooks for subscription events
    """
    print("............................................StripeWebhookView.......................................")
    permission_classes = []  # No authentication required for webhooks

    def post(self, request):
        try:
            get_stripe_client()
            
            # Get webhook secret
            webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET') or getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
            if not webhook_secret:
                return HttpResponse("Webhook secret not configured", status=400)
            
            # Get the webhook signature
            sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
            if not sig_header:
                return HttpResponse("Missing Stripe signature", status=400)
            
            # Verify webhook signature
            try:
                event = stripe.Webhook.construct_event(
                    request.body, sig_header, webhook_secret
                )
            except ValueError as e:
                return HttpResponse(f"Invalid payload: {e}", status=400)
            except stripe.error.SignatureVerificationError as e:
                return HttpResponse(f"Invalid signature: {e}", status=400)
            
            # Check if we've already processed this event (idempotency)
            event_id = event['id']
            if WebhookEvent.objects.filter(stripe_event_id=event_id).exists():
                print(f"📋 Event {event_id} already processed, skipping")
                return HttpResponse("Event already processed", status=200)
            
            print(f"🎣 Processing webhook event: {event['type']} ({event_id})")
            
            # Handle the event based on type
            try:
                if event['type'] == 'customer.subscription.updated':
                    self._handle_subscription_updated(event['data']['object'])
                elif event['type'] == 'customer.subscription.deleted':
                    self._handle_subscription_deleted(event['data']['object'])
                elif event['type'] == 'invoice.payment_succeeded':
                    self._handle_payment_succeeded(event['data']['object'])
                elif event['type'] == 'invoice.payment_failed':
                    self._handle_payment_failed(event['data']['object'])
                elif event['type'] == 'customer.subscription.trial_will_end':
                    self._handle_trial_ending(event['data']['object'])
                elif event['type'] == 'setup_intent.succeeded':
                    self._handle_setup_intent_succeeded(event['data']['object'])
                elif event['type'] == 'payment_intent.canceled':
                    self._handle_payment_intent_canceled(event['data']['object'])
                elif event['type'] == 'setup_intent.canceled':
                    self._handle_setup_intent_canceled(event['data']['object'])
                elif event['type'] == 'invoice.voided':
                    self._handle_invoice_voided(event['data']['object'])
                elif event['type'] == 'invoice.updated':
                    self._handle_invoice_updated(event['data']['object'])
                    
                else:
                    print(f"ℹ️ Unhandled event type: {event['type']}")
                
                # Log successful processing
                WebhookEvent.objects.create(
                    stripe_event_id=event_id,
                    type=event['type'],
                    payload=event['data']
                )
                
                print(f"✅ Successfully processed webhook: {event['type']}")
                
            except Exception as handler_error:
                print(f"❌ Error processing webhook {event['type']}: {handler_error}")
                import traceback
                traceback.print_exc()
                raise handler_error
            
            return HttpResponse("Webhook processed successfully", status=200)
            
        except Exception as e:
            return HttpResponse(f"Webhook error: {str(e)}", status=500)
    
    def _handle_checkout_completed(self, session):
        """Handle successful checkout session"""
        print("............................................_handle_checkout_completed.......................................")

        try:
            customer_id = session.get('customer')
            if not customer_id:
                return
            
            # Get or create customer account
            customer = CustomerAccount.objects.get(stripe_customer_id=customer_id)
            
            # If it's a subscription, create subscription record
            if session.get('mode') == 'subscription':
                subscription_id = session.get('subscription')
                if subscription_id:
                    # Get subscription details from Stripe
                    stripe_sub = stripe.Subscription.retrieve(subscription_id)
                    
                    # Find the course from the price
                    price_id = stripe_sub['items']['data'][0]['price']['id']
                    try:
                        billing_price = BillingPrice.objects.get(stripe_price_id=price_id)
                        course = billing_price.product.course
                        
                        # Create subscription record
                        Subscribers.objects.create(
                            user=customer.user,
                            course=course,
                            stripe_subscription_id=subscription_id,
                            stripe_price_id=price_id,
                            status=stripe_sub['status'],
                            current_period_start=timezone.datetime.fromtimestamp(
                                stripe_sub['current_period_start'], tz=timezone.utc
                            ),
                            current_period_end=timezone.datetime.fromtimestamp(
                                stripe_sub['current_period_end'], tz=timezone.utc
                            ),
                        )
                    except BillingPrice.DoesNotExist:
                        pass
                        
        except Exception as e:
            print(f"Error handling checkout completed: {e}")
    


    def _handle_setup_intent_succeeded(self, setup_intent):
        """Fired once the user entered card details and Stripe successfully attached it to the customer/subscription"""
        print(f"✅ Webhook: Setup intent {setup_intent['id']} succeeded")
        try:
            # Get subscription ID from setup intent
            # Setup intents don't have subscription field, so we need to find it via customer
            customer_id = setup_intent.get('customer')
            setup_intent_id = setup_intent.get('id')
            
            # Find the subscription that has this setup intent as its pending_setup_intent
            subscription_id = None
            if customer_id:
                try:
                    # Query Stripe to find which subscription has this setup intent
                    # This is more reliable than guessing from database
                    get_stripe_client()
                    subscriptions = stripe.Subscription.list(
                        customer=customer_id,
                        status='all',
                        limit=10,
                        expand=['data.pending_setup_intent']
                    )
                    
                    for sub in subscriptions.data:
                        if hasattr(sub, 'pending_setup_intent') and sub.pending_setup_intent:
                            if sub.pending_setup_intent.id == setup_intent_id:
                                subscription_id = sub.id
                                print(f"✅ Found subscription {subscription_id} with matching setup intent {setup_intent_id}")
                                break
                    
                    # Fallback: If not found via Stripe query, try database lookup
                    if not subscription_id:
                        try:
                            # Get customer account to find user
                            customer_account = CustomerAccount.objects.get(stripe_customer_id=customer_id)
                            # Find the most recent incomplete subscription for this user
                            recent_subscriber = Subscribers.objects.filter(
                                user=customer_account.user,
                                status='incomplete'
                            ).order_by('-created_at').first()
                            
                            if recent_subscriber:
                                subscription_id = recent_subscriber.stripe_subscription_id
                                print(f"⚠️ Fallback: Found subscription {subscription_id} from database for customer {customer_id}")
                            else:
                                print(f"⚠️ No incomplete subscription found for customer {customer_id}")
                        except CustomerAccount.DoesNotExist:
                            print(f"⚠️ Customer account not found for {customer_id}")
                except Exception as e:
                    print(f"❌ Error finding subscription for setup intent: {e}")
                    import traceback
                    traceback.print_exc()
            if subscription_id:
                try:
                    # Get the subscription from Stripe to check if it has a trial period
                    get_stripe_client()
                    stripe_subscription = stripe.Subscription.retrieve(subscription_id)
                    metadata = stripe_subscription.get('metadata', {})
                    has_trial_period = metadata.get('trial_period', 'false').lower() == 'true'
                    trial_period_days = stripe_subscription.get('trial_period_days', 0)
                    has_trial = has_trial_period or (trial_period_days and trial_period_days > 0)
                    
                    # Update Subscribers table
                    subscriber = Subscribers.objects.get(stripe_subscription_id=subscription_id)
                    
                    if has_trial:
                        # For subscriptions WITH trial: setup_intent succeeded means trial started
                        subscriber.status = 'trialing'
                        subscriber.save()
                        print(f"✅ Updated subscriber {subscriber.id} to trialing status (trial started)")
                        
                        # CRITICAL: Ensure enrollment is created when trial starts
                        print(f"🎓 Webhook: Ensuring enrollment is created for trial subscription {subscription_id}")
                        try:
                            course_id = metadata.get('course_id')
                            class_id = metadata.get('class_id')
                            pricing_type = metadata.get('pricing_type', 'one_time')
                            
                            print(f"🔍 Webhook: Processing trial subscription {subscription_id} - Course: {course_id}, Class: {class_id}")
                            
                            if course_id and class_id:
                                from courses.models import Course
                                course = Course.objects.get(id=course_id)
                                user = subscriber.user
                                
                                # Call complete_enrollment_process to ensure enrollment exists
                                enrollment = complete_enrollment_process(
                                    subscription_id=subscription_id,
                                    user=user,
                                    course=course,
                                    class_id=class_id,
                                    pricing_type=pricing_type,
                                    is_trial=True
                                )
                                
                                if enrollment:
                                    print(f"✅ Webhook: Enrollment ensured for trial subscription {subscription_id}")
                                else:
                                    print(f"⚠️ Webhook: Failed to ensure enrollment for subscription {subscription_id}")
                            else:
                                print(f"⚠️ Webhook: Missing metadata for subscription {subscription_id}: course_id={course_id}, class_id={class_id}")
                                
                        except Exception as e:
                            print(f"❌ Webhook: Error ensuring enrollment: {e}")
                            import traceback
                            traceback.print_exc()
                    else:
                        # For subscriptions WITHOUT trial: setup_intent succeeded means payment method collected
                        # For default_incomplete subscriptions, we need to manually pay the invoice
                        print(f"💳 Setup intent succeeded for non-trial subscription {subscription_id}")
                        
                        # Update subscriber status to active (payment method collected, invoice will be paid)
                        subscriber.status = 'active'
                        subscriber.save()
                        print(f"✅ Updated subscriber {subscriber.id} to active status (payment method collected)")
                        
                        # CRITICAL: Ensure enrollment is created when payment method is collected
                        print(f"🎓 Webhook: Ensuring enrollment is created for non-trial subscription {subscription_id}")
                        try:
                            course_id = metadata.get('course_id')
                            class_id = metadata.get('class_id')
                            pricing_type = metadata.get('pricing_type', 'one_time')
                            
                            print(f"🔍 Webhook: Processing non-trial subscription {subscription_id} - Course: {course_id}, Class: {class_id}")
                            
                            if course_id and class_id:
                                from courses.models import Course
                                course = Course.objects.get(id=course_id)
                                user = subscriber.user
                                is_trial = False  # Non-trial subscription
                                
                                # Call complete_enrollment_process to ensure enrollment exists
                                enrollment = complete_enrollment_process(
                                    subscription_id=subscription_id,
                                    user=user,
                                    course=course,
                                    class_id=class_id,
                                    pricing_type=pricing_type,
                                    is_trial=is_trial
                                )
                                
                                if enrollment:
                                    print(f"✅ Webhook: Enrollment ensured for non-trial subscription {subscription_id}")
                                else:
                                    print(f"⚠️ Webhook: Failed to ensure enrollment for subscription {subscription_id}")
                            else:
                                print(f"⚠️ Webhook: Missing metadata for subscription {subscription_id}: course_id={course_id}, class_id={class_id}")
                                
                        except Exception as e:
                            print(f"❌ Webhook: Error ensuring enrollment: {e}")
                            import traceback
                            traceback.print_exc()
                        
                        try:
                            # Get the latest invoice for this subscription
                            latest_invoice_id = stripe_subscription.get('latest_invoice')
                            if latest_invoice_id:
                                # Retrieve the invoice to check status
                                invoice = stripe.Invoice.retrieve(latest_invoice_id, expand=['payment_intent'])
                                
                                if invoice.status == 'paid':
                                    print(f"✅ Invoice {latest_invoice_id} is already paid - triggering payment succeeded handler")
                                    # Trigger payment succeeded handler manually
                                    self._handle_payment_succeeded(invoice)
                                elif invoice.status in ['open', 'draft']:
                                    # For non-trial subscriptions, manually pay the invoice
                                    print(f"💳 Attempting to pay invoice {latest_invoice_id} for non-trial subscription")
                                    try:
                                        # Add a small delay to ensure payment method is fully attached
                                        import time
                                        time.sleep(0.5)
                                        
                                        paid_invoice = stripe.Invoice.pay(latest_invoice_id)
                                        if paid_invoice.status == 'paid':
                                            print(f"✅ Invoice {latest_invoice_id} paid successfully")
                                            # Trigger payment succeeded handler
                                            self._handle_payment_succeeded(paid_invoice)
                                        else:
                                            print(f"⚠️ Invoice payment attempt returned status: {paid_invoice.status}")
                                            print(f"ℹ️ Will wait for invoice.payment_succeeded webhook")
                                    except stripe.error.InvalidRequestError as e:
                                        error_code = getattr(e, 'code', None)
                                        error_message = str(e)
                                        print(f"⚠️ Could not pay invoice automatically: {error_message} (code: {error_code})")
                                        
                                        # If payment method not ready, wait for Stripe to process
                                        if 'payment_method' in error_message.lower() or error_code == 'payment_intent_unexpected_state':
                                            print(f"ℹ️ Payment method may not be ready yet - Stripe will attempt payment automatically")
                                            print(f"ℹ️ Will wait for invoice.payment_succeeded webhook")
                                        else:
                                            # Other errors - log and wait
                                            print(f"ℹ️ Will wait for invoice.payment_succeeded webhook")
                                else:
                                    print(f"ℹ️ Invoice {latest_invoice_id} status is {invoice.status} - waiting for payment")
                            else:
                                print(f"⚠️ No latest invoice found for subscription {subscription_id}")
                        except Exception as e:
                            print(f"⚠️ Error attempting to pay invoice: {e}")
                            import traceback
                            traceback.print_exc()
                            print(f"ℹ️ Will wait for invoice.payment_succeeded webhook")
                    
                except Subscribers.DoesNotExist:
                    print(f"⚠️ Subscriber {subscription_id} not found for payment succeeded")
            else:
                print(f"❌ ..............................Subscriber {subscription_id} not found for payment succeeded")
        except Exception as e:
            print(f"❌ Error handling setup intent succeeded: {e}")
            import traceback
            traceback.print_exc()

    def _create_payment_record_from_setup(self, subscription_id, setup_intent_id):
        """Create payment record when setup intent succeeds"""
        try:
            # Get subscriber to access user and course info
            subscriber = Subscribers.objects.get(stripe_subscription_id=subscription_id)
            
            # Check if payment already exists
            existing_payment = Payment.objects.filter(
                user=subscriber.user,
                course=subscriber.course,
                stripe_payment_intent_id=setup_intent_id
            ).first()
            
            if existing_payment:
                print(f"✅ Payment record already exists for setup intent {setup_intent_id}")
                return
            
            # Get invoice details from Stripe subscription
            stripe_invoice_id = ''
            amount = 0.00
            currency = 'usd'
            status = 'requires_confirmation'
            paid_at = None
            
            try:
                # Get the subscription from Stripe to find the latest invoice
                stripe_subscription = stripe.Subscription.retrieve(subscription_id)
                latest_invoice_id = stripe_subscription.get('latest_invoice')
                
                if latest_invoice_id:
                    # Get the invoice details
                    stripe_invoice = stripe.Invoice.retrieve(latest_invoice_id)
                    stripe_invoice_id = stripe_invoice.get('id', '')
                    amount = stripe_invoice.get('amount_paid', 0) / 100  # Convert from cents
                    currency = stripe_invoice.get('currency', 'usd')
                    
                    # If invoice is paid, update status
                    if stripe_invoice.get('status') == 'paid':
                        status = 'succeeded'
                        # Convert Unix timestamp to timezone-aware datetime
                        paid_at_timestamp = stripe_invoice.get('status_transitions', {}).get('paid_at')
                        if paid_at_timestamp:
                            from datetime import datetime
                            from django.utils import timezone
                            paid_at = timezone.make_aware(datetime.fromtimestamp(paid_at_timestamp))
                        else:
                            paid_at = None
                    
                else:
                    print(f"⚠️ No invoice found for subscription {subscription_id}")
                    
            except Exception as e:
                print(f"⚠️ Error fetching invoice details: {e}")
                # Continue with default values
            
            # Create payment record with invoice details
            payment = Payment.objects.create(
                user=subscriber.user,
                course=subscriber.course,
                stripe_payment_intent_id=setup_intent_id,
                stripe_invoice_id=stripe_invoice_id,
                amount=amount,
                currency=currency,
                status=status,
                paid_at=paid_at
            )
            
            print(f"✅ Created payment record {payment.id} for setup intent {setup_intent_id}")
            
        except Subscribers.DoesNotExist:
            print(f"❌ Subscriber not found for subscription {subscription_id}")
        except Exception as e:
            print(f"❌ Error creating payment record: {e}")
            import traceback
            traceback.print_exc()



    
    def _handle_subscription_created(self, subscription):
        """Handle subscription creation"""
        # This is handled in checkout_completed for our use case
        print(f"🔍 Webhook: Subscription {subscription['id']} creation received")
        pass
    
    def _handle_subscription_updated(self, subscription):
        """Handle subscription updates"""
        print(f"🔍 Webhook: Subscription {subscription['id']} update received")
        print("........................................................................................................................_handle_subscription_updated.......................................")
        try:
            subscriber = Subscribers.objects.get(stripe_subscription_id=subscription['id'])
            old_status = subscriber.status
            new_status = subscription['status']
            
            print(f"🔍 Webhook: Subscription {subscription['id']} status change: {old_status} → {new_status}")
            
            # Update status
            subscriber.status = new_status
            subscriber.save()
            
            # CRITICAL: Ensure enrollment is created when subscription becomes active/trialing
            if new_status in ['active', 'trialing'] and old_status in ['incomplete', 'incomplete_expired']:
                print(f"🎓 Webhook: Ensuring enrollment is created for subscription {subscription['id']}")
                try:
                    # Get metadata from Stripe subscription
                    metadata = subscription.get('metadata', {})
                    course_id = metadata.get('course_id')
                    class_id = metadata.get('class_id')
                    pricing_type = metadata.get('pricing_type', 'one_time')
                    
                    print(f"🔍 Webhook: Metadata extraction for subscription {subscription['id']}:")
                    print(f"   - Full metadata: {metadata}")
                    print(f"   - course_id: {course_id}")
                    print(f"   - class_id: {class_id}")
                    print(f"   - pricing_type: {pricing_type}")
                    
                    if course_id and class_id:
                        from courses.models import Course
                        course = Course.objects.get(id=course_id)
                        user = subscriber.user
                        is_trial = new_status == 'trialing'
                        
                        # Call complete_enrollment_process to ensure enrollment exists
                        enrollment = complete_enrollment_process(
                            subscription_id=subscription['id'],
                            user=user,
                            course=course,
                            class_id=class_id,
                            pricing_type=pricing_type,
                            is_trial=is_trial
                        )
                        
                        if enrollment:
                            print(f"✅ Webhook: Enrollment ensured for subscription {subscription['id']}")
                        else:
                            print(f"⚠️ Webhook: Failed to ensure enrollment for subscription {subscription['id']}")
                    else:
                        print(f"⚠️ Webhook: Missing metadata for subscription {subscription['id']}: course_id={course_id}, class_id={class_id}")
                        
                except Exception as e:
                    print(f"❌ Webhook: Error ensuring enrollment: {e}")
                    import traceback
                    traceback.print_exc()
            
            # If subscription becomes active (trial ended), update subscription type
            if new_status == 'active' and old_status == 'trialing':
                print(f"🔄 Trial ended, updating subscription type from trial to actual pricing type")
                update_subscription_type_from_stripe(subscription['id'])
            
            # Update next_invoice_date and next_invoice_amount from Stripe subscription
            try:
                from datetime import datetime
                # Get current_period_end as next invoice date for active subscriptions
                if subscription.get('current_period_end'):
                    next_invoice_date = datetime.fromtimestamp(
                        subscription['current_period_end'], tz=timezone.utc
                    )
                    subscriber.next_invoice_date = next_invoice_date
                    print(f"📅 Updated next_invoice_date to {next_invoice_date}")
                
                # Get next invoice amount from subscription items
                if subscription.get('items', {}).get('data', []):
                    item = subscription['items']['data'][0]
                    next_invoice_amount = item.get('price', {}).get('unit_amount', 0) / 100
                    if next_invoice_amount > 0:
                        subscriber.next_invoice_amount = next_invoice_amount
                        print(f"💰 Updated next_invoice_amount to ${next_invoice_amount}")
                
                # Also update current_period_start and current_period_end
                if subscription.get('current_period_start'):
                    subscriber.current_period_start = datetime.fromtimestamp(
                        subscription['current_period_start'], tz=timezone.utc
                    )
                if subscription.get('current_period_end'):
                    subscriber.current_period_end = datetime.fromtimestamp(
                        subscription['current_period_end'], tz=timezone.utc
                    )
                
                subscriber.save()
            except Exception as e:
                print(f"⚠️ Error updating invoice dates: {e}")
            
            print(f"✅ Updated subscriber {subscriber.id}: {old_status} → {new_status}")
            
        except Subscribers.DoesNotExist:
            print(f"⚠️ Subscriber {subscription['id']} not found for update")
        except Exception as e:
            print(f"❌ Error handling subscription updated: {e}")
            import traceback
            traceback.print_exc()
        
        
    
    def _handle_subscription_deleted(self, subscription):
        """Handle subscription cancellation"""
        try:
            sub = Subscribers.objects.get(stripe_subscription_id=subscription['id'])
            sub.status = 'canceled'
            sub.canceled_at = timezone.now()
            sub.save()
        except Subscribers.DoesNotExist:
            pass
        except Exception as e:
            print(f"Error handling subscription deleted: {e}")
    
    def _handle_payment_succeeded(self, invoice):
        """Handle successful invoice payment - updates subscription status and creates enrollment"""
        try:
            invoice_id = invoice.get('id')
            subscription_id = invoice.get('subscription')
            invoice_status = invoice.get('status')
            amount_paid = invoice.get('amount_paid', 0) / 100  # Convert from cents
            currency = invoice.get('currency', 'usd')
            
            print(f"💰 Invoice payment succeeded: {invoice_id} for subscription {subscription_id}")
            print(f"💰 Amount paid: ${amount_paid} {currency}")
            
            if not subscription_id:
                print(f"⚠️ Invoice {invoice_id} has no subscription - skipping")
                return
            
            # Get subscriber record
            try:
                subscriber = Subscribers.objects.get(stripe_subscription_id=subscription_id)
            except Subscribers.DoesNotExist:
                print(f"⚠️ Subscriber {subscription_id} not found for invoice payment")
                return
            
            # Get subscription from Stripe to check metadata and status
            get_stripe_client()
            stripe_subscription = stripe.Subscription.retrieve(subscription_id)
            metadata = stripe_subscription.get('metadata', {})
            subscription_status = stripe_subscription.get('status')
            
            # Check if this is a trial subscription or paid subscription
            has_trial_period = metadata.get('trial_period', 'false').lower() == 'true'
            trial_period_days = stripe_subscription.get('trial_period_days', 0)
            has_trial = has_trial_period or (trial_period_days and trial_period_days > 0)
            pricing_type = metadata.get('pricing_type', 'monthly')
            
            # Update subscription status and type
            if has_trial:
                # Trial subscription - payment succeeded means trial ended, first charge happened
                subscriber.status = 'active'
                subscriber.subscription_type = pricing_type  # Update from 'trial' to actual type
                print(f"✅ Trial ended - updated subscriber {subscriber.id} to active status, type: {pricing_type}")
            else:
                # Non-trial subscription - payment succeeded means subscription is now active
                subscriber.status = 'active'
                subscriber.subscription_type = pricing_type
                print(f"✅ Payment succeeded - updated subscriber {subscriber.id} to active status, type: {pricing_type}")
            
            # Update next_invoice_date and next_invoice_amount from Stripe subscription
            try:
                from datetime import datetime
                # Get current_period_end as next invoice date for active subscriptions
                if stripe_subscription.get('current_period_end'):
                    next_invoice_date = datetime.fromtimestamp(
                        stripe_subscription['current_period_end'], tz=timezone.utc
                    )
                    subscriber.next_invoice_date = next_invoice_date
                    print(f"📅 Updated next_invoice_date to {next_invoice_date}")
                
                # Get next invoice amount from subscription items
                if stripe_subscription.get('items', {}).get('data', []):
                    item = stripe_subscription['items']['data'][0]
                    next_invoice_amount = item.get('price', {}).get('unit_amount', 0) / 100
                    if next_invoice_amount > 0:
                        subscriber.next_invoice_amount = next_invoice_amount
                        print(f"💰 Updated next_invoice_amount to ${next_invoice_amount}")
                
                # Also update current_period_start and current_period_end
                if stripe_subscription.get('current_period_start'):
                    subscriber.current_period_start = datetime.fromtimestamp(
                        stripe_subscription['current_period_start'], tz=timezone.utc
                    )
                if stripe_subscription.get('current_period_end'):
                    subscriber.current_period_end = datetime.fromtimestamp(
                        stripe_subscription['current_period_end'], tz=timezone.utc
                    )
            except Exception as e:
                print(f"⚠️ Error updating invoice dates from payment succeeded: {e}")
            
            subscriber.save()
            
            # Create or update Payment record
            try:
                Payment.objects.update_or_create(
                    stripe_invoice_id=invoice_id,
                    defaults={
                        'user': subscriber.user,
                        'course': subscriber.course,
                        'amount': amount_paid,
                        'currency': currency,
                        'status': 'succeeded',
                        'paid_at': timezone.now(),
                    }
                )
                print(f"✅ Payment record created/updated for invoice {invoice_id}")
            except Exception as e:
                print(f"⚠️ Error creating payment record: {e}")
            
            # CRITICAL: Ensure enrollment is created when payment succeeds
            print(f"🎓 Webhook: Ensuring enrollment is created for subscription {subscription_id}")
            try:
                course_id = metadata.get('course_id')
                class_id = metadata.get('class_id')
                
                if course_id and class_id:
                    from courses.models import Course
                    course = Course.objects.get(id=course_id)
                    user = subscriber.user
                    
                    # For non-trial subscriptions, payment succeeded means paid enrollment
                    # For trial subscriptions, payment succeeded means trial ended and first charge happened
                    is_trial = False  # Payment succeeded means it's no longer a trial
                    
                    # Call complete_enrollment_process to ensure enrollment exists
                    enrollment = complete_enrollment_process(
                        subscription_id=subscription_id,
                        user=user,
                        course=course,
                        class_id=class_id,
                        pricing_type=pricing_type,
                        is_trial=is_trial
                    )
                    
                    if enrollment:
                        print(f"✅ Webhook: Enrollment ensured for subscription {subscription_id}")
                    else:
                        print(f"⚠️ Webhook: Failed to ensure enrollment for subscription {subscription_id}")
                else:
                    print(f"⚠️ Webhook: Missing metadata for subscription {subscription_id}: course_id={course_id}, class_id={class_id}")
                    
            except Exception as e:
                print(f"❌ Webhook: Error ensuring enrollment: {e}")
                import traceback
                traceback.print_exc()
                
        except Exception as e:
            print(f"❌ Error handling payment succeeded: {e}")
            import traceback
            traceback.print_exc()
       
    def _handle_payment_failed(self, invoice):
        """Handle failed payment"""
        try:
            subscription_id = invoice.get('subscription')
            if subscription_id:
                try:
                    sub = Subscribers.objects.get(stripe_subscription_id=subscription_id)
                    sub.status = 'past_due'
                    sub.save()
                    print(f"✅ Updated subscriber {subscription_id} to past_due")
                except Subscribers.DoesNotExist:
                    print(f"⚠️ Subscriber {subscription_id} not found for failed payment")
        except Exception as e:
            print(f"❌ Error handling payment failed: {e}")
    
    def _handle_trial_ending(self, subscription):
        """Handle trial ending notification"""
        try:
            sub = Subscribers.objects.get(stripe_subscription_id=subscription['id'])
            print(f"⏰ Trial ending soon for subscription {subscription['id']}")
            print(f"📧 TODO: Send trial ending email to user {sub.user.email}")
            # Here you could send an email notification to the user
        except Subscribers.DoesNotExist:
            print(f"⚠️ Subscriber {subscription['id']} not found for trial ending")
        except Exception as e:
            print(f"❌ Error handling trial ending: {e}")
    
    def _handle_payment_intent_canceled(self, payment_intent):
        """Handle when user cancels payment intent without entering card details"""
        try:
            payment_intent_id = payment_intent['id']
            print(f"🚫 Payment intent canceled: {payment_intent_id}")
            
            # Update any payment records associated with this payment intent
            payments = Payment.objects.filter(stripe_payment_intent_id=payment_intent_id)
            print(f"🔍 Found {payments.count()} payment records for canceled payment intent")
            
            for payment in payments:
                if payment.status != 'canceled':
                    payment.status = 'canceled'
                    payment.save(update_fields=['status'])
                    print(f"✅ Updated payment {payment.id} status to canceled")
                
        except Exception as e:
            print(f"❌ Error handling payment intent canceled: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_setup_intent_canceled(self, setup_intent):
        """Handle when user cancels setup intent for subscription"""
        try:
            setup_intent_id = setup_intent['id']
            print(f"🚫 Setup intent canceled: {setup_intent_id}")
            
            # Update any payment records associated with this setup intent
            payments = Payment.objects.filter(stripe_payment_intent_id=setup_intent_id)
            print(f"🔍 Found {payments.count()} payment records for canceled setup intent")
            
            for payment in payments:
                if payment.status != 'canceled':
                    payment.status = 'canceled'
                    payment.save(update_fields=['status'])
                    print(f"✅ Updated payment {payment.id} status to canceled")
                
        except Exception as e:
            print(f"❌ Error handling setup intent canceled: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_invoice_voided(self, invoice):
        """Handle when invoice is voided (usually means payment was canceled)"""
        try:
            invoice_id = invoice.get('id')
            print(f"🚫 Invoice voided: {invoice_id}")
            
            # Update any payment records associated with this invoice
            payments = Payment.objects.filter(stripe_invoice_id=invoice_id)
            print(f"🔍 Found {payments.count()} payment records for voided invoice")
            
            for payment in payments:
                if payment.status != 'canceled':
                    payment.status = 'canceled'
                    payment.save(update_fields=['status'])
                    print(f"✅ Updated payment {payment.id} status to canceled (invoice voided)")
                
        except Exception as e:
            print(f"❌ Error handling invoice voided: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_invoice_updated(self, invoice):
        """Handle when invoice is updated (status changes, etc.)"""
        try:
            invoice_id = invoice.get('id')
            invoice_status = invoice.get('status')
            print(f"🔄 Invoice updated: {invoice_id} (status: {invoice_status})")
            
            # Update payment records based on invoice status
            payments = Payment.objects.filter(stripe_invoice_id=invoice_id)
            
            for payment in payments:
                # Map invoice status to payment status
                if invoice_status == 'paid' and payment.status != 'succeeded':
                    payment.status = 'succeeded'
                    # Get paid_at timestamp if available
                    paid_at_timestamp = invoice.get('status_transitions', {}).get('paid_at')
                    if paid_at_timestamp:
                        from datetime import datetime
                        from django.utils import timezone
                        payment.paid_at = timezone.make_aware(datetime.fromtimestamp(paid_at_timestamp))
                    payment.save(update_fields=['status', 'paid_at'])
                    print(f"✅ Updated payment {payment.id} status to succeeded (invoice paid)")
                elif invoice_status == 'void' and payment.status != 'canceled':
                    payment.status = 'canceled'
                    payment.save(update_fields=['status'])
                    print(f"✅ Updated payment {payment.id} status to canceled (invoice voided)")
                elif invoice_status == 'uncollectible' and payment.status != 'canceled':
                    # Mark as canceled if invoice is uncollectible (no valid status for failed in Payment model)
                    payment.status = 'canceled'
                    payment.save(update_fields=['status'])
                    print(f"✅ Updated payment {payment.id} status to canceled (invoice uncollectible)")
                
        except Exception as e:
            print(f"❌ Error handling invoice updated: {e}")
            import traceback
            traceback.print_exc()


class CreatePaymentIntentView(APIView):
    """
    Create the correct Stripe payment object for the selected pricing plan.

    - For pricing_type == 'one_time':
      Creates a one-time PaymentIntent using the course's one-time price.

    - For pricing_type == 'monthly':
      Creates a Subscription (trial-aware when requested) using the course's
      monthly price. The latest invoice's PaymentIntent client_secret is
      returned for Stripe Elements confirmation.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id: str):
        print(f"🔍 CreatePaymentIntentView called with course_id: {course_id}")
        print(f"🔍 Request data: {request.data}")
        print(f"🔍 User: {request.user}")
        
        # Check if user already has active subscriptions for this course
        try:
            existing_subs = Subscribers.objects.filter(
                user=request.user,
                course_id=course_id,
                status__in=['active', 'trialing', 'incomplete', 'incomplete_expired', 'past_due']
            )
            print(f"🔍 Found {existing_subs.count()} existing subscribers for this user/course")
            for sub in existing_subs:
                print(f"  - Subscriber {sub.stripe_subscription_id}: status={sub.status}, created={sub.created_at}")
        except Exception as e:
            print(f"⚠️ Error checking existing subscribers: {e}")
        
        try:
            stripe_client = get_stripe_client()
            print(f"🔑 Stripe client configured with key: {stripe.api_key[:12]}...")
            # Check if we're in test or live mode
            is_test_mode = stripe.api_key.startswith('sk_test_')
            print(f"🔑 Stripe mode: {'TEST' if is_test_mode else 'LIVE'}")
            
            # Get course
            course = get_object_or_404(Course, id=course_id, status='published')
            pricing_type = request.data.get('pricing_type', 'one_time')
            
            # Get billing data for the course
            try:
                billing_product = BillingProduct.objects.get(course=course)
                # Get pricing options from billing prices (active only)
                one_time_price = BillingPrice.objects.filter(
                    product=billing_product, billing_period='one_time', is_active=True
                ).first()
                monthly_price = BillingPrice.objects.filter(
                    product=billing_product, billing_period='monthly', is_active=True
                ).first()
                
                pricing_options = {
                    'one_time': {'amount': float(one_time_price.unit_amount) if one_time_price else float(course.price)},
                    'monthly': {'amount': float(monthly_price.unit_amount) if monthly_price else float(course.price) * 1.15}
                }
                print(f"💰 Course pricing options: {pricing_options}")
            except BillingProduct.DoesNotExist:
                print(f"⚠️ No billing product found for course {course.id}, using base price")
                pricing_options = {
                    'one_time': {'amount': float(course.price)},
                    'monthly': {'amount': float(course.price) * 1.15}  # 15% more for installments
                }
            
            # Ensure customer exists in current environment (auto-migrate if needed)
            stripe_customer_id = ensure_stripe_customer_in_current_environment(request.user)
            
            # Calculate amount based on pricing type
            if pricing_type == 'monthly':
                amount = int(pricing_options['monthly']['amount'] * 100)
                print(f"💳 Creating subscription for monthly payment: ${pricing_options['monthly']['amount']}")
                
                # Calculate total months for the course duration
                import math
                total_months = math.ceil(course.duration_weeks / 4)
                print(f"📅 Course duration: {course.duration_weeks} weeks = {total_months} months")
                
                # Ensure product and prices exist in current environment (auto-migrate if needed)
                try:
                    stripe_price_id = ensure_stripe_product_and_prices_in_current_environment(
                        course, 
                        billing_period='monthly'
                    )
                    print(f"✅ Using price ID: {stripe_price_id} (verified in current environment)")
                except Exception as e:
                    print(f"❌ Failed to ensure product/prices in current environment: {e}")
                    # Fallback: Try to create price on the fly (legacy behavior)
                    try:
                        billing_product = BillingProduct.objects.get(course=course)
                        monthly_price = BillingPrice.objects.filter(
                            product=billing_product, 
                            billing_period='monthly',
                            is_active=True
                        ).first()
                        if monthly_price:
                            stripe_price_id = monthly_price.stripe_price_id
                        else:
                            raise BillingPrice.DoesNotExist
                    except (BillingProduct.DoesNotExist, BillingPrice.DoesNotExist):
                        # Create a price on the fly if it doesn't exist
                        stripe_price = stripe.Price.create(
                            unit_amount=amount,
                            currency='usd',
                            recurring={'interval': 'month'},
                            product_data={
                                'name': f"{course.title} - Monthly Subscription",
                            },
                            metadata={
                                'course_id': str(course.id),
                                'pricing_type': 'monthly'
                            }
                        )
                        stripe_price_id = stripe_price.id
                
                # Create subscription
                #print(f"🚀 About to create Stripe subscription with price_id: {stripe_price_id}")
                #print(f"🚀 Customer: {customer_account.stripe_customer_id}")
                # Get trial period settings
                trial_settings = get_trial_period_settings()
                # Only use trial if explicitly requested AND enabled AND days > 0
                has_trial = (request.data.get('trial_period') and 
                            trial_settings['enabled'] and 
                            trial_settings['days'] > 0)
                trial_days = trial_settings['days'] if has_trial else 0
                print(f"🚀 Trial period: {trial_days} days (has_trial: {has_trial})")
                
                try:
                    # Calculate when to cancel the subscription after all monthly payments
                    import datetime
                    from datetime import timezone as dt_timezone
                    # Cancel after trial + (total_months * 30 days per month)
                    cancel_at = datetime.datetime.now(dt_timezone.utc) + datetime.timedelta(
                        days=trial_days + (total_months * 30)
                    )
                    print(f"🗓️ Monthly subscription will cancel: {cancel_at.strftime('%Y-%m-%d %H:%M:%S UTC')} (after {total_months} payments)")
                    
                    # Try to create subscription - if it fails due to invalid price, migrate and retry
                    max_retries = 1
                    retry_count = 0
                    subscription = None
                    
                    while retry_count <= max_retries and subscription is None:
                        try:
                            # Only pass trial_period_days if trial_days > 0
                            # If trial_days is 0, pass None (no trial period)
                            # Payment behavior: Use 'default_incomplete' for trials (creates setup intent)
                            # For no trial, we still use 'default_incomplete' but Stripe should create setup intent for payment method collection
                            subscription_params = {
                                'customer': stripe_customer_id,
                                'items': [{'price': stripe_price_id}],
                                'cancel_at': int(cancel_at.timestamp()),  # Cancel after specified number of monthly payments
                                'payment_behavior': 'default_incomplete',  # Always use this - creates setup intent for payment method collection
                                'payment_settings': {
                                    'save_default_payment_method': 'on_subscription',
                                    'payment_method_types': ['card']  # Explicitly specify payment method types
                                },
                                'collection_method': 'charge_automatically',  # Ensure automatic charging
                                'expand': ['latest_invoice.payment_intent', 'pending_setup_intent'],
                                'metadata': {
                                    'course_id': str(course.id),
                                    'course_title': course.title,
                                    'user_id': str(request.user.id),
                                    'user_email': request.user.email,
                                    'pricing_type': pricing_type,  # Store the original pricing choice
                                    'trial_period': str(has_trial).lower(),
                                    'class_id': str(request.data.get('class_id', '')),
                                    'student_profile_id': str(getattr(request.user, 'student_profile', {}).id if hasattr(request.user, 'student_profile') and request.user.student_profile else '')
                                }
                            }
                            
                            # Only add trial_period_days if we have a valid trial (days > 0)
                            if has_trial and trial_days > 0:
                                subscription_params['trial_period_days'] = trial_days
                                print(f"✅ Adding trial period: {trial_days} days")
                            else:
                                print(f"ℹ️ No trial period (trial_days={trial_days}, has_trial={has_trial})")
                                # When no trial, ensure we get a setup intent for payment method collection
                                # Stripe should create this automatically with default_incomplete, but we'll verify in retry logic
                            
                            subscription = stripe.Subscription.create(**subscription_params)
                            print(f"✅ Subscription created successfully with price {stripe_price_id}")
                        except stripe.error.InvalidRequestError as e:
                            error_code = getattr(e, 'code', '')
                            error_message = str(e)
                            
                            # Check if error is due to invalid price ID (wrong environment)
                            if ('No such price' in error_message or 
                                error_code == 'resource_missing' or
                                'price' in error_message.lower()):
                                if retry_count < max_retries:
                                    print(f"⚠️ Subscription creation failed due to invalid price ID: {e}")
                                    print(f"🔄 Retrying with migrated product/prices...")
                                    # Migrate product and prices, then retry
                                    stripe_price_id = ensure_stripe_product_and_prices_in_current_environment(
                                        course, 
                                        billing_period='monthly'
                                    )
                                    print(f"✅ Migrated to new price ID: {stripe_price_id}, retrying subscription creation...")
                                    retry_count += 1
                                else:
                                    # Max retries reached, raise the error
                                    print(f"❌ Max retries reached, price migration failed")
                                    raise e
                            else:
                                # Different error, don't retry
                                raise e
                    #print(f"✅ Stripe subscription created: {subscription.id}")
                   # print(f"✅ Subscription status: {subscription.status}")
                   # print(f"🔍 Metadata sent to Stripe: {subscription.metadata}")
                   # print(f"🔍 DEBUG: class_id from request: {request.data.get('class_id')}")
                   # print(f"🔍 DEBUG: class_id in metadata: {subscription.metadata.get('class_id')}")
                   # print(f"✅ Has latest_invoice: {bool(getattr(subscription, 'latest_invoice', None))}")
                   # print(f"✅ Has pending_setup_intent: {bool(getattr(subscription, 'pending_setup_intent', None))}")
                    
                    # Create local subscription record immediately with incomplete status
                    #print(f"🔄 Creating local subscription record for: {subscription.id}")
                    try:
                        # Get the price ID from the subscription
                        stripe_price_id = subscription['items']['data'][0]['price']['id']
                        
                        # Calculate period dates (handle trial vs active subscriptions)
                        from datetime import datetime
                        
                        # For trial subscriptions, current_period_start/end might not exist
                        # Use trial_start/trial_end instead
                        if subscription.get('current_period_start'):
                            current_period_start = datetime.fromtimestamp(
                                subscription['current_period_start'], tz=timezone.utc
                            )
                        elif subscription.get('trial_start'):
                            current_period_start = datetime.fromtimestamp(
                                subscription['trial_start'], tz=timezone.utc
                            )
                        else:
                            # Fallback to creation time
                            current_period_start = datetime.fromtimestamp(
                                subscription['created'], tz=timezone.utc
                            )
                        
                        if subscription.get('current_period_end'):
                            current_period_end = datetime.fromtimestamp(
                                subscription['current_period_end'], tz=timezone.utc
                            )
                        elif subscription.get('trial_end'):
                            current_period_end = datetime.fromtimestamp(
                                subscription['trial_end'], tz=timezone.utc
                            )
                        else:
                            # Fallback: Use trial period settings for trials
                            from datetime import timedelta
                            trial_settings = get_trial_period_settings()
                            trial_days = trial_settings['days'] if trial_settings['enabled'] else 14
                            current_period_end = current_period_start + timedelta(days=trial_days)
                        
                        # Handle cancel_at field safely
                        cancel_at = None
                        if subscription.get('cancel_at'):
                            cancel_at = datetime.fromtimestamp(
                                subscription['cancel_at'], tz=timezone.utc
                            )
                        
                        # Get billing interval from the price
                        billing_interval = 'one_time'  # Default
                        if subscription.get('items', {}).get('data', []):
                            price_data = subscription['items']['data'][0]['price']
                            if price_data.get('recurring'):
                                billing_interval = price_data['recurring'].get('interval', 'monthly')
                            else:
                                billing_interval = 'one_time'
                        
                        # Calculate next invoice date and amount
                        next_invoice_date = None
                        next_invoice_amount = None
                        
                        # For trial subscriptions, next invoice is after trial ends
                        if subscription.get('trial_end'):
                            next_invoice_date = datetime.fromtimestamp(
                                subscription['trial_end'], tz=timezone.utc
                            )
                        elif subscription.get('current_period_end'):
                            next_invoice_date = datetime.fromtimestamp(
                                subscription['current_period_end'], tz=timezone.utc
                            )
                        
                            # Get the amount from the subscription items
                            if subscription.get('items', {}).get('data', []):
                                item = subscription['items']['data'][0]
                                next_invoice_amount = item.get('price', {}).get('unit_amount', 0) / 100
                        
                        # Next invoice data calculated
                        
                        # Get trial end date
                        trial_end = None
                        if subscription.get('trial_end'):
                            trial_end = datetime.fromtimestamp(
                                subscription['trial_end'], tz=timezone.utc
                            )
                        
                        # Get current subscription amount
                        subscription_amount = None
                        if subscription.get('items', {}).get('data', []):
                            item = subscription['items']['data'][0]
                            subscription_amount = item.get('price', {}).get('unit_amount', 0) / 100
                        
                        # Create local subscriber record with incomplete status for trial subscriptions
                        # Initially set as trial, will update to monthly/one_time when payment completes
                        subscription_type = 'trial'
                        
                        local_subscriber = Subscribers.objects.create(
                            user=request.user,
                            course=course,
                            stripe_subscription_id=subscription.id,
                            stripe_price_id=stripe_price_id,
                            status='incomplete',  # Trial subscriptions start as incomplete
                            subscription_type=subscription_type,
                            current_period_start=current_period_start,
                            current_period_end=current_period_end,
                            cancel_at=cancel_at,
                            next_invoice_date=next_invoice_date,
                            next_invoice_amount=next_invoice_amount,
                            trial_end=trial_end,
                            billing_interval=billing_interval,
                            amount=subscription_amount,
                        )
                        
                        print(f"✅ Local subscriber record created: {local_subscriber.id} with status: incomplete")
                        
                    except Exception as e:
                        print(f"⚠️ Could not save local subscription: {e}")
                        import traceback
                        traceback.print_exc()
                        # Don't raise - we still want to return the Stripe subscription
                    
                    # Double-check by retrieving the subscription from Stripe
                    try:
                        verified_sub = stripe.Subscription.retrieve(subscription.id)
                        print(f"🔍 Verified subscription exists in Stripe: {verified_sub.id} (status: {verified_sub.status})")
                    except Exception as verify_error:
                        print(f"❌ Failed to verify subscription in Stripe: {verify_error}")
                
                except stripe.error.StripeError as e:
                    print(f"❌ Stripe error creating subscription: {e}")
                    print(f"❌ Error type: {type(e).__name__}")
                    print(f"❌ Error code: {getattr(e, 'code', 'N/A')}")
                    raise e
                except Exception as e:
                    print(f"❌ Unexpected error creating subscription: {e}")
                    print(f"❌ Error type: {type(e).__name__}")
                    raise e
                
                # For incomplete subscriptions, Stripe provides a pending_setup_intent for PM collection
                # When no trial period, Stripe may create a payment_intent for immediate charge
                # When trial period exists, Stripe creates a setup_intent for future payment
                # NOTE: Stripe may need a moment to create intents, so we retry with delays
                intent_type = 'payment'
                client_secret = None
                payment_intent_id = None
                setup_intent_id = None
                
                # Retry mechanism: Stripe sometimes needs a moment to create intents
                import time
                max_retries = 3
                retry_delays = [0.1, 0.3, 0.5]  # 100ms, 300ms, 500ms
                
                for attempt in range(max_retries):
                    if attempt > 0:
                        # Wait before retrying (except first attempt)
                        delay = retry_delays[attempt - 1]
                        print(f"⏳ Waiting {delay}s before retry {attempt} to get payment/setup intent...")
                        time.sleep(delay)
                        
                        # Re-retrieve subscription with expanded fields to get latest state
                        print(f"🔄 Re-retrieving subscription {subscription.id} with expanded fields...")
                        subscription = stripe.Subscription.retrieve(
                            subscription.id,
                            expand=['latest_invoice.payment_intent', 'pending_setup_intent']
                        )
                    
                    # Check for payment intent first (for immediate charges, no trial)
                    if getattr(subscription, 'latest_invoice', None):
                        latest_invoice = subscription.latest_invoice
                        if hasattr(latest_invoice, 'payment_intent') and latest_invoice.payment_intent:
                            payment_intent = latest_invoice.payment_intent
                            client_secret = payment_intent.client_secret
                            payment_intent_id = payment_intent.id
                            intent_type = 'payment'
                            print(f"💳 Using payment intent from latest_invoice: {payment_intent_id}")
                            break  # Found intent, exit retry loop
                    
                    # Check for setup intent (for trials or future payments)
                    if not client_secret and getattr(subscription, 'pending_setup_intent', None):
                        setup_intent = subscription.pending_setup_intent
                        client_secret = setup_intent.client_secret
                        setup_intent_id = setup_intent.id
                        intent_type = 'setup'
                        print(f"🔧 Using setup intent: {setup_intent_id}")
                        break  # Found intent, exit retry loop
                    
                    # If still no intent, try to retrieve from invoice directly
                    if not client_secret and subscription.get('latest_invoice'):
                        try:
                            invoice = stripe.Invoice.retrieve(
                                subscription.latest_invoice,
                                expand=['payment_intent']
                            )
                            if invoice.payment_intent:
                                payment_intent = invoice.payment_intent
                                client_secret = payment_intent.client_secret
                                payment_intent_id = payment_intent.id
                                intent_type = 'payment'
                                print(f"💳 Retrieved payment intent from invoice: {payment_intent_id}")
                                break  # Found intent, exit retry loop
                        except Exception as e:
                            print(f"⚠️ Could not retrieve payment intent from invoice: {e}")
                    
                    # If we found an intent, break out of retry loop
                    if client_secret:
                        break
                    
                    # Log attempt if not last one
                    if attempt < max_retries - 1:
                        print(f"⚠️ Attempt {attempt + 1}: No payment or setup intent found yet, will retry...")
                        print(f"⚠️ Subscription status: {subscription.status}, latest_invoice: {subscription.get('latest_invoice')}")
                
                # Final check: if still no intent after all retries, try to update subscription to get intent
                if not client_secret:
                    print(f"⚠️ No payment or setup intent found after {max_retries} attempts")
                    print(f"⚠️ Subscription ID: {subscription.id}, Status: {subscription.status}")
                    print(f"⚠️ Latest invoice: {subscription.get('latest_invoice')}")
                    print(f"⚠️ Pending setup intent: {subscription.get('pending_setup_intent')}")
                    
                    # Try one more time: update subscription to ensure setup intent is created
                    if not has_trial and subscription.status == 'incomplete':
                        print(f"🔄 No trial and subscription is incomplete - attempting to update subscription to get setup intent...")
                        try:
                            # Update subscription to ensure payment method collection
                            updated_subscription = stripe.Subscription.modify(
                                subscription.id,
                                payment_behavior='default_incomplete',
                                payment_settings={
                                    'save_default_payment_method': 'on_subscription',
                                    'payment_method_types': ['card']
                                },
                                expand=['latest_invoice.payment_intent', 'pending_setup_intent']
                            )
                            
                            # Check again for setup intent
                            if getattr(updated_subscription, 'pending_setup_intent', None):
                                setup_intent = updated_subscription.pending_setup_intent
                                client_secret = setup_intent.client_secret
                                setup_intent_id = setup_intent.id
                                intent_type = 'setup'
                                print(f"✅ Got setup intent after subscription update: {setup_intent_id}")
                            elif getattr(updated_subscription, 'latest_invoice', None):
                                latest_invoice = updated_subscription.latest_invoice
                                if hasattr(latest_invoice, 'payment_intent') and latest_invoice.payment_intent:
                                    payment_intent = latest_invoice.payment_intent
                                    client_secret = payment_intent.client_secret
                                    payment_intent_id = payment_intent.id
                                    intent_type = 'payment'
                                    print(f"✅ Got payment intent after subscription update: {payment_intent_id}")
                        except Exception as e:
                            print(f"⚠️ Failed to update subscription to get intent: {e}")
                    
                    # If still no intent, raise error
                    if not client_secret:
                        print(f"❌ No payment or setup intent available after all attempts")
                        print(f"❌ Subscription ID: {subscription.id}, Status: {subscription.status}")
                        raise Exception('No payment or setup intent available for subscription')
                
            else:
                amount = int(pricing_options['one_time']['amount'] * 100)
                print(f"💳 Creating one-time payment: ${pricing_options['one_time']['amount']}")
                
                # Check if trial is requested and valid (days > 0)
                trial_settings = get_trial_period_settings()
                has_trial_one_time = (request.data.get('trial_period') and 
                                     trial_settings['enabled'] and 
                                     trial_settings['days'] > 0)
                
                if has_trial_one_time:
                    # For one-time payments with trial, create a subscription that will charge once and then cancel
                    trial_days = trial_settings['days']
                    print(f"🔄 Creating one-time subscription with trial ({trial_days} days) for: ${pricing_options['one_time']['amount']}")
                    
                    # For subscriptions, we need a recurring price, not a one-time price
                    # Create a special recurring price for one-time trial subscriptions
                    stripe_price = stripe.Price.create(
                        unit_amount=amount,
                        currency='usd',
                        recurring={'interval': 'month'},  # Required for subscriptions, but will cancel after first payment
                        product_data={
                            'name': f"{course.title} - One-time Payment (Trial)",
                        },
                        metadata={
                            'course_id': str(course.id),
                            'pricing_type': 'one_time_trial'
                        }
                    )
                    stripe_price_id = stripe_price.id
                    print(f"✅ Created recurring price for one-time trial: {stripe_price_id}")
                    
                    # Create a subscription with trial that will cancel after first payment
                    try:
                        import datetime
                        from datetime import timezone as dt_timezone
                        
                        # Calculate when to cancel: trial end + 1 billing cycle (1 month)
                        trial_end = datetime.datetime.now(dt_timezone.utc) + datetime.timedelta(days=trial_days)
                        cancel_at = trial_end + datetime.timedelta(days=30)  # 1 month after trial ends
                        print(f"🗓️ Trial ends: {trial_end.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                        print(f"🗓️ Subscription will cancel: {cancel_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                        
                        subscription = stripe.Subscription.create(
                            customer=stripe_customer_id,
                            items=[{'price': stripe_price_id}],
                            trial_period_days=trial_days,  # Only called if has_trial_one_time is True, so trial_days > 0
                            cancel_at=int(cancel_at.timestamp()),  # Cancel after first payment
                            payment_behavior='default_incomplete',
                            payment_settings={'save_default_payment_method': 'on_subscription'},
                            expand=['latest_invoice.payment_intent', 'pending_setup_intent'],
                            metadata={
                                'course_id': str(course.id),
                                'course_title': course.title,
                                'user_id': str(request.user.id),
                                'user_email': request.user.email,
                                'pricing_type': pricing_type,  # Store the original pricing choice
                                'trial_period': 'true',
                                'class_id': str(request.data.get('class_id', '')),
                                'student_profile_id': str(getattr(request.user, 'student_profile', {}).id if hasattr(request.user, 'student_profile') and request.user.student_profile else '')
                            }
                        )
                        print(f"✅ One-time trial subscription created: {subscription.id}")
                        print(f"✅ Subscription status: {subscription.status}")
                        print(f"🔍 Metadata sent to Stripe: {subscription.metadata}")
                        print(f"⏰ Stripe subscription created at: {timezone.now()}")
                        
                        # Create local subscription record immediately with incomplete status
                        print(f"🔄 Creating local subscription record for one-time trial: {subscription.id}")
                        try:
                            # Get the price ID from the subscription
                            stripe_price_id = subscription['items']['data'][0]['price']['id']
                            
                            # Calculate period dates (handle trial vs active subscriptions)
                            from datetime import datetime
                            
                            # For trial subscriptions, current_period_start/end might not exist
                            # Use trial_start/trial_end instead
                            if subscription.get('current_period_start'):
                                current_period_start = datetime.fromtimestamp(
                                    subscription['current_period_start'], tz=timezone.utc
                                )
                            elif subscription.get('trial_start'):
                                current_period_start = datetime.fromtimestamp(
                                    subscription['trial_start'], tz=timezone.utc
                                )
                            else:
                                # Fallback to creation time
                                current_period_start = datetime.fromtimestamp(
                                    subscription['created'], tz=timezone.utc
                                )
                            
                            if subscription.get('current_period_end'):
                                current_period_end = datetime.fromtimestamp(
                                    subscription['current_period_end'], tz=timezone.utc
                                )
                            elif subscription.get('trial_end'):
                                current_period_end = datetime.fromtimestamp(
                                    subscription['trial_end'], tz=timezone.utc
                                )
                            else:
                                # Fallback: Use trial period settings for trials
                                from datetime import timedelta
                                trial_settings = get_trial_period_settings()
                                trial_days = trial_settings['days'] if trial_settings['enabled'] else 14
                                current_period_end = current_period_start + timedelta(days=trial_days)
                            
                            # Handle cancel_at field safely
                            cancel_at = None
                            if subscription.get('cancel_at'):
                                cancel_at = datetime.fromtimestamp(
                                    subscription['cancel_at'], tz=timezone.utc
                                )
                            
                            # Get billing interval from the price
                            billing_interval = 'one_time'  # Default
                            if subscription.get('items', {}).get('data', []):
                                price_data = subscription['items']['data'][0]['price']
                                if price_data.get('recurring'):
                                    billing_interval = price_data['recurring'].get('interval', 'monthly')
                                else:
                                    billing_interval = 'one_time'
                            
                            # Calculate next invoice date and amount
                            next_invoice_date = None
                            next_invoice_amount = None
                            
                            # For one-time trial subscriptions, next invoice is after trial ends
                            if subscription.get('trial_end'):
                                next_invoice_date = datetime.fromtimestamp(
                                    subscription['trial_end'], tz=timezone.utc
                                )
                                # For one-time payments, the amount is the total course price
                                next_invoice_amount = pricing_options['one_time']['amount']
                                # One-time trial: Next invoice data calculated
                            elif subscription.get('current_period_end'):
                                next_invoice_date = datetime.fromtimestamp(
                                    subscription['current_period_end'], tz=timezone.utc
                                )
                                # Get the amount from the subscription items
                                if subscription.get('items', {}).get('data', []):
                                    item = subscription['items']['data'][0]
                                    next_invoice_amount = item.get('price', {}).get('unit_amount', 0) / 100
                            
                            # Get trial end date
                            trial_end = None
                            if subscription.get('trial_end'):
                                trial_end = datetime.fromtimestamp(
                                    subscription['trial_end'], tz=timezone.utc
                                )
                            
                            # Get current subscription amount
                            subscription_amount = None
                            if subscription.get('items', {}).get('data', []):
                                item = subscription['items']['data'][0]
                                subscription_amount = item.get('price', {}).get('unit_amount', 0) / 100
                            
                            # Create local subscriber record with incomplete status for trial subscriptions
                            try:
                                # Initially set as trial, will update to one_time when payment completes
                                subscription_type = 'trial'
                                
                                local_subscriber = Subscribers.objects.create(
                                    user=request.user,
                                    course=course,
                                    stripe_subscription_id=subscription.id,
                                    stripe_price_id=stripe_price_id,
                                    status='incomplete',  # Trial subscriptions start as incomplete
                                    subscription_type=subscription_type,
                                    current_period_start=current_period_start,
                                    current_period_end=current_period_end,
                                    cancel_at=cancel_at,
                                    next_invoice_date=next_invoice_date,
                                    next_invoice_amount=next_invoice_amount,
                                    trial_end=trial_end,
                                    billing_interval=billing_interval,
                                    amount=subscription_amount,
                                )
                                
                                print(f"✅ Local one-time trial subscriber record created: {local_subscriber.id} with status: incomplete")
                            
                            except Exception as e:
                                print(f"⚠️ Could not save local one-time trial subscription: {e}")
                                import traceback
                                traceback.print_exc()
                                # Don't raise - we still want to return the Stripe subscription
                        
                            # Handle the intents like monthly subscriptions
                            # Use same retry mechanism as monthly subscriptions to handle timing issues
                            import time
                            intent_type = 'payment'
                            client_secret = None
                            payment_intent_id = None
                            setup_intent_id = None
                            
                            # Retry mechanism: Stripe sometimes needs a moment to create intents
                            max_retries = 3
                            retry_delays = [0.1, 0.3, 0.5]  # 100ms, 300ms, 500ms
                            
                            for attempt in range(max_retries):
                                if attempt > 0:
                                    # Wait before retrying (except first attempt)
                                    delay = retry_delays[attempt - 1]
                                    print(f"⏳ Waiting {delay}s before retry {attempt} to get payment/setup intent (one-time)...")
                                    time.sleep(delay)
                                    
                                    # Re-retrieve subscription with expanded fields to get latest state
                                    print(f"🔄 Re-retrieving subscription {subscription.id} with expanded fields...")
                                    subscription = stripe.Subscription.retrieve(
                                        subscription.id,
                                        expand=['latest_invoice.payment_intent', 'pending_setup_intent']
                                    )
                                
                                # Check for payment intent first (for immediate charges, no trial)
                                if getattr(subscription, 'latest_invoice', None):
                                    latest_invoice = subscription.latest_invoice
                                    if hasattr(latest_invoice, 'payment_intent') and latest_invoice.payment_intent:
                                        payment_intent = latest_invoice.payment_intent
                                        client_secret = payment_intent.client_secret
                                        payment_intent_id = payment_intent.id
                                        intent_type = 'payment'
                                        print(f"💳 Using payment intent from latest_invoice: {payment_intent_id}")
                                        break  # Found intent, exit retry loop
                                
                                # Check for setup intent (for trials or future payments)
                                if not client_secret and getattr(subscription, 'pending_setup_intent', None):
                                    setup_intent = subscription.pending_setup_intent
                                    client_secret = setup_intent.client_secret
                                    setup_intent_id = setup_intent.id
                                    intent_type = 'setup'
                                    print(f"🔧 Using setup intent: {setup_intent_id}")
                                    break  # Found intent, exit retry loop
                                
                                # If still no intent, try to retrieve from invoice directly
                                if not client_secret and subscription.get('latest_invoice'):
                                    try:
                                        invoice = stripe.Invoice.retrieve(
                                            subscription.latest_invoice,
                                            expand=['payment_intent']
                                        )
                                        if invoice.payment_intent:
                                            payment_intent = invoice.payment_intent
                                            client_secret = payment_intent.client_secret
                                            payment_intent_id = payment_intent.id
                                            intent_type = 'payment'
                                            print(f"💳 Retrieved payment intent from invoice: {payment_intent_id}")
                                            break  # Found intent, exit retry loop
                                    except Exception as e:
                                        print(f"⚠️ Could not retrieve payment intent from invoice: {e}")
                                
                                # If we found an intent, break out of retry loop
                                if client_secret:
                                    break
                                
                                # Log attempt if not last one
                                if attempt < max_retries - 1:
                                    print(f"⚠️ Attempt {attempt + 1}: No payment or setup intent found yet (one-time), will retry...")
                                    print(f"⚠️ Subscription status: {subscription.status}, latest_invoice: {subscription.get('latest_invoice')}")
                            
                            # Final check: if still no intent after all retries, try to update subscription
                            if not client_secret:
                                print(f"⚠️ No payment or setup intent found after {max_retries} attempts (one-time)")
                                print(f"⚠️ Subscription ID: {subscription.id}, Status: {subscription.status}")
                                print(f"⚠️ Latest invoice: {subscription.get('latest_invoice')}")
                                print(f"⚠️ Pending setup intent: {subscription.get('pending_setup_intent')}")
                                
                                # Try to update subscription to get intent (same as monthly)
                                if not has_trial_one_time and subscription.status == 'incomplete':
                                    print(f"🔄 No trial and subscription is incomplete - attempting to update subscription...")
                                    try:
                                        updated_subscription = stripe.Subscription.modify(
                                            subscription.id,
                                            payment_behavior='default_incomplete',
                                            payment_settings={
                                                'save_default_payment_method': 'on_subscription',
                                                'payment_method_types': ['card']
                                            },
                                            expand=['latest_invoice.payment_intent', 'pending_setup_intent']
                                        )
                                        
                                        if getattr(updated_subscription, 'pending_setup_intent', None):
                                            setup_intent = updated_subscription.pending_setup_intent
                                            client_secret = setup_intent.client_secret
                                            setup_intent_id = setup_intent.id
                                            intent_type = 'setup'
                                            print(f"✅ Got setup intent after subscription update: {setup_intent_id}")
                                        elif getattr(updated_subscription, 'latest_invoice', None):
                                            latest_invoice = updated_subscription.latest_invoice
                                            if hasattr(latest_invoice, 'payment_intent') and latest_invoice.payment_intent:
                                                payment_intent = latest_invoice.payment_intent
                                                client_secret = payment_intent.client_secret
                                                payment_intent_id = payment_intent.id
                                                intent_type = 'payment'
                                                print(f"✅ Got payment intent after subscription update: {payment_intent_id}")
                                    except Exception as e:
                                        print(f"⚠️ Failed to update subscription to get intent: {e}")
                                
                                if not client_secret:
                                    print(f"❌ No payment or setup intent available after all attempts (one-time)")
                                    raise Exception('No payment or setup intent available for subscription')
                        except Exception as e:
                            print(f"⚠️ Could not save local one-time trial subscription: {e}")
                            import traceback
                            traceback.print_exc()
                            # Don't raise - we still want to return the Stripe subscription
                            
                    except stripe.error.StripeError as e:
                        print(f"❌ Stripe error creating one-time trial subscription: {e}")
                        print(f"❌ Error type: {type(e).__name__}")
                        print(f"❌ Error code: {getattr(e, 'code', 'N/A')}")
                        raise e
                    except Exception as e:
                        print(f"❌ Unexpected error creating one-time trial subscription: {e}")
                        print(f"❌ Error type: {type(e).__name__}")
                        raise e
                        
                else:
                    # For immediate one-time payments (no trial)
                    payment_intent = stripe.PaymentIntent.create(
                        amount=amount,
                        currency='usd',
                        customer=stripe_customer_id,
                        metadata={
                            'course_id': str(course.id),
                            'course_title': course.title,
                            'user_id': str(request.user.id),
                            'user_email': request.user.email,
                            'pricing_type': 'one_time'
                        },
                        description=f"Enrollment in {course.title}",
                    )
                    intent_type = 'payment'
                    client_secret = payment_intent.client_secret
                    payment_intent_id = payment_intent.id
                    setup_intent_id = None
            
            # Determine subscription_id for response
            subscription_id = None
            if pricing_type == 'monthly':
                subscription_id = subscription.id
            elif pricing_type == 'one_time' and request.data.get('trial_period') and 'subscription' in locals():
                subscription_id = subscription.id
            
            response_data = {
                'client_secret': client_secret,
                'intent_type': intent_type,
                'payment_intent_id': payment_intent_id,
                'setup_intent_id': setup_intent_id,
                'subscription_id': subscription_id,
                'amount': amount / 100,  # Convert from cents to dollars for frontend
                'currency': 'usd',
                'course_title': course.title,
            }
            
            print(f"🎯 Final response data: {response_data}")
            
            # Add a delayed check to see if status changes after request completes
            import threading
            import time
            
            def delayed_status_check(subscription_id, delay=5):
                time.sleep(delay)
                try:
                    sub = Subscribers.objects.get(id=subscription_id)
                    print(f"🔍 DELAYED CHECK ({delay}s later): Subscription {subscription_id} status = {sub.status}")
                    if sub.status != 'incomplete':
                        print(f"🚨 STATUS CHANGED AFTER REQUEST! Now: {sub.status}")
                except Exception as e:
                    print(f"⚠️ Delayed check failed: {e}")
            
            # Start delayed check in background
            if subscription_id and 'local_subscriber' in locals():
                thread = threading.Thread(target=delayed_status_check, args=(local_subscriber.id, 5))
                thread.daemon = True
                thread.start()
                print(f"🔍 Started delayed status check for subscription {local_subscriber.id}")
            
            return Response({
                'client_secret': client_secret,
                'intent_type': intent_type,  # 'payment' | 'setup'
                'payment_intent_id': payment_intent_id,
                'setup_intent_id': setup_intent_id,
                'subscription_id': subscription_id,
                'amount': amount,
                'currency': 'usd',
                'course_title': course.title,
            }, status=status.HTTP_200_OK)
            
        except Course.DoesNotExist:
            return Response(
                {'error': 'Course not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"Error creating payment intent: {e}")
            return Response(
                {'error': 'Failed to create payment intent', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ConfirmEnrollmentView(APIView):
    """
    Poll and wait for webhook to complete enrollment process
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id: str):
        print(f"🎓 CONFIRM ENROLLMENT: {course_id}")
        
        try:
            # Get course and class
            course = get_object_or_404(Course, id=course_id, status='published')
            class_id = request.data.get('class_id')
            subscription_id = request.data.get('subscription_id')
            payment_intent_id = request.data.get('payment_intent_id')
            is_trial = request.data.get('trial_period', False)
            pricing_type = request.data.get('pricing_type', 'one_time')
            
            if not class_id:
                return Response(
                    {'error': 'Class ID is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # For one-time payments without trial, payment_intent_id is required instead of subscription_id
            # For subscriptions (monthly or one-time with trial), subscription_id is required
            if not subscription_id and not payment_intent_id:
                return Response(
                    {'error': 'Either Subscription ID or Payment Intent ID is required for enrollment confirmation'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # If it's a one-time payment without subscription, handle it differently
            if payment_intent_id and not subscription_id:
                return self._handle_one_time_payment_enrollment(
                    request, course, class_id, payment_intent_id, pricing_type
                )
            
            # Get the class
            from courses.models import Class
            selected_class = get_object_or_404(Class, id=class_id)
            
            # Poll for webhook completion (max 15 seconds)
            import time
            max_wait_time = 15  # seconds
            poll_interval = 0.5  # seconds
            start_time = time.time()
            
            print(f"🔄 Polling for webhook completion...")
            
            while time.time() - start_time < max_wait_time:
                try:
                    # Check if subscriber status changed to trialing
                    subscriber = Subscribers.objects.get(stripe_subscription_id=subscription_id)
                    if subscriber.status == 'trialing':
                        # Check if enrollment was created by webhook
                        from student.models import EnrolledCourse
                        enrollment = EnrolledCourse.objects.filter(
                            student_profile__user=request.user,
                            course=course
                        ).first()
                        
                        if enrollment:
                            print(f"✅ Enrollment completed by webhook: {enrollment.id}")
                            
                            # Check if it's a trial enrollment
                            trial_end_date = None
                            if is_trial and hasattr(enrollment, 'payment_due_date') and enrollment.payment_due_date:
                                trial_end_date = enrollment.payment_due_date
                            
                            return Response({
                                'message': f'{"Trial" if is_trial else "Paid"} enrollment successful',
                                'enrollment_id': str(enrollment.id),
                                'is_trial': is_trial,
                                'trial_end_date': trial_end_date.isoformat() if trial_end_date else None
                            }, status=status.HTTP_201_CREATED)
                    
                    time.sleep(poll_interval)
                    
                except Subscribers.DoesNotExist:
                    time.sleep(poll_interval)
                except Exception as e:
                    print(f"❌ Error during polling: {e}")
                    time.sleep(poll_interval)
            
            # Timeout reached - webhook didn't arrive, query Stripe directly
            print(f"⏰ Timeout: Webhook did not complete enrollment within {max_wait_time} seconds")
            print(f"🔍 Querying Stripe directly to verify payment status...")
            
            try:
                # Query Stripe to check subscription and payment status
                get_stripe_client()
                print(f"🔍 Attempting to retrieve subscription from Stripe: {subscription_id}")
                stripe_subscription = stripe.Subscription.retrieve(
                    subscription_id,
                    expand=['latest_invoice.payment_intent', 'pending_setup_intent']
                )
                print(f"✅ Successfully retrieved subscription from Stripe: {stripe_subscription.id}")
                
                subscription_status = stripe_subscription.get('status')
                print(f"📊 Stripe subscription status: {subscription_status}")
                
                # Also check setup intent status if subscription is incomplete
                setup_intent_status = None
                setup_intent_id = None
                if subscription_status == 'incomplete':
                    # Check if setup intent exists and its status
                    if hasattr(stripe_subscription, 'pending_setup_intent') and stripe_subscription.pending_setup_intent:
                        setup_intent_id = stripe_subscription.pending_setup_intent.id
                        try:
                            setup_intent = stripe.SetupIntent.retrieve(setup_intent_id)
                            setup_intent_status = setup_intent.status
                            print(f"📊 Setup intent status: {setup_intent_status} (ID: {setup_intent_id})")
                        except Exception as e:
                            print(f"⚠️ Could not retrieve setup intent: {e}")
                
                # Check if payment was successful based on subscription status
                # 'trialing' = trial started (payment method collected, no charge yet)
                # 'active' = subscription active (payment succeeded)
                # 'incomplete' = payment method not collected or payment failed
                #   BUT: if setup_intent.status == 'succeeded', payment method WAS collected
                # 'incomplete_expired' = payment method collection expired
                # 'past_due' = payment failed
                
                # Payment successful if:
                # 1. Subscription is trialing/active, OR
                # 2. Subscription is incomplete BUT setup intent succeeded (payment method collected, waiting for first charge)
                payment_successful = (
                    subscription_status in ['trialing', 'active'] or
                    (subscription_status == 'incomplete' and setup_intent_status == 'succeeded')
                )
                
                # Handle incomplete status with succeeded setup intent
                if subscription_status == 'incomplete' and setup_intent_status == 'succeeded':
                    # Setup intent succeeded but subscription still incomplete - check invoice status
                    # If invoice payment failed, we should not treat this as success
                    latest_invoice_id = stripe_subscription.get('latest_invoice')
                    if latest_invoice_id:
                        try:
                            invoice = stripe.Invoice.retrieve(latest_invoice_id)
                            invoice_status = invoice.get('status')
                            print(f"🔍 Invoice status: {invoice_status} for invoice {latest_invoice_id}")
                            
                            if invoice_status == 'paid':
                                # Invoice is paid - payment was successful
                                print(f"✅ Invoice is paid - payment successful")
                                payment_successful = True
                            elif invoice_status in ['open', 'draft']:
                                # Invoice is open - check if payment was attempted and failed
                                last_payment_error = invoice.get('last_payment_error')
                                if last_payment_error:
                                    # Payment was attempted but failed
                                    error_message = last_payment_error.get('message', 'Payment failed')
                                    print(f"❌ Invoice payment failed: {error_message}")
                                    return Response(
                                        {'error': f'Payment failed: {error_message}. Please check your payment method and try again.'}, 
                                        status=status.HTTP_402_PAYMENT_REQUIRED
                                    )
                                # Invoice is open - payment method collected, waiting for payment
                                # This can happen when trial_days=0 and subscription is waiting for first charge
                                print(f"✅ Setup intent succeeded - payment method collected successfully")
                                print(f"ℹ️ Invoice is {invoice_status} - payment method is ready, waiting for charge")
                                payment_successful = True
                            elif invoice_status in ['void', 'uncollectible']:
                                # Invoice payment failed - return error immediately
                                print(f"❌ Invoice payment failed (status: {invoice_status})")
                                return Response(
                                    {'error': 'Payment failed. Your payment method was collected but the charge was declined. Please check your payment method and try again.'}, 
                                    status=status.HTTP_402_PAYMENT_REQUIRED
                                )
                            else:
                                # Unknown invoice status - be cautious
                                print(f"⚠️ Unknown invoice status: {invoice_status}")
                                payment_successful = False
                        except Exception as e:
                            print(f"⚠️ Error checking invoice status: {e}")
                            # If we can't check invoice, assume payment method is ready
                            print(f"ℹ️ Assuming payment method is ready (setup intent succeeded)")
                            payment_successful = True
                    else:
                        # No invoice yet - payment method is ready
                        print(f"✅ Setup intent succeeded - payment method collected successfully")
                        print(f"ℹ️ No invoice yet - payment method is ready")
                        payment_successful = True
                
                if payment_successful:
                    # Payment was successful - create enrollment directly
                    if subscription_status == 'incomplete' and setup_intent_status == 'succeeded':
                        print(f"✅ Stripe confirms payment method collected (setup intent succeeded, subscription incomplete)")
                        print(f"ℹ️ Subscription is incomplete but setup intent succeeded - payment method is ready")
                    else:
                        print(f"✅ Stripe confirms payment successful (status: {subscription_status})")
                    print(f"🔄 Creating enrollment directly since webhook didn't arrive...")
                    
                    # Get subscription metadata
                    metadata = stripe_subscription.get('metadata', {})
                    course_id_from_stripe = metadata.get('course_id')
                    class_id_from_stripe = metadata.get('class_id')
                    pricing_type_from_stripe = metadata.get('pricing_type', 'one_time')
                    
                    # Use metadata from Stripe if available, otherwise use request data
                    final_course_id = course_id_from_stripe or course_id
                    final_class_id = class_id_from_stripe or class_id
                    final_pricing_type = pricing_type_from_stripe or request.data.get('pricing_type', 'one_time')
                    
                    # Determine if it's a trial based on subscription status and trial_end
                    has_trial_period = subscription_status == 'trialing' or stripe_subscription.get('trial_end') is not None
                    
                    # Get or create subscriber record
                    # Use get_or_create to avoid duplicate key errors (unique constraint on user+course)
                    subscriber, created = Subscribers.objects.get_or_create(
                        user=request.user,
                        course=course,
                        defaults={
                            'stripe_subscription_id': subscription_id,
                            'status': subscription_status,
                            'subscription_type': 'trial' if has_trial_period else final_pricing_type
                        }
                    )
                    
                    # Update subscriber if it already existed or if status changed
                    if not created:
                        # Subscriber already exists - update it
                        updated_fields = []
                        if subscriber.stripe_subscription_id != subscription_id:
                            subscriber.stripe_subscription_id = subscription_id
                            updated_fields.append('stripe_subscription_id')
                        if subscriber.status != subscription_status:
                            subscriber.status = subscription_status
                            updated_fields.append('status')
                        if subscriber.subscription_type != ('trial' if has_trial_period else final_pricing_type):
                            subscriber.subscription_type = 'trial' if has_trial_period else final_pricing_type
                            updated_fields.append('subscription_type')
                        
                        if updated_fields:
                            updated_fields.append('updated_at')
                            subscriber.save(update_fields=updated_fields)
                            print(f"✅ Updated existing subscriber {subscriber.id} with fields: {updated_fields}")
                        else:
                            print(f"✅ Subscriber {subscriber.id} already exists and is up to date")
                    else:
                        print(f"✅ Created new subscriber record: {subscriber.id}")
                    
                    # Create enrollment using complete_enrollment_process
                    enrollment = complete_enrollment_process(
                        subscription_id=subscription_id,
                        user=request.user,
                        course=course,
                        class_id=final_class_id,
                        pricing_type=final_pricing_type,
                        is_trial=has_trial_period
                    )
                    
                    if enrollment:
                        print(f"✅ Enrollment created directly after Stripe verification: {enrollment.id}")
                        
                        # Get trial end date if applicable
                        trial_end_date = None
                        if has_trial_period:
                            trial_end_timestamp = stripe_subscription.get('trial_end')
                            if trial_end_timestamp:
                                from datetime import datetime, timezone as dt_timezone
                                trial_end_date = datetime.fromtimestamp(trial_end_timestamp, tz=dt_timezone.utc).date()
                            elif hasattr(enrollment, 'payment_due_date') and enrollment.payment_due_date:
                                trial_end_date = enrollment.payment_due_date
                        
                        return Response({
                            'message': f'{"Trial" if has_trial_period else "Paid"} enrollment successful (verified via Stripe)',
                            'enrollment_id': str(enrollment.id),
                            'is_trial': has_trial_period,
                            'trial_end_date': trial_end_date.isoformat() if trial_end_date else None,
                            'verified_via': 'stripe_direct_query'
                        }, status=status.HTTP_201_CREATED)
                    else:
                        print(f"❌ Failed to create enrollment after Stripe verification")
                        return Response(
                            {'error': 'Payment verified but enrollment creation failed. Please contact support.'}, 
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )
                
                elif subscription_status in ['incomplete', 'incomplete_expired']:
                    # Payment method not collected or expired
                    # (If setup intent succeeded, we already handled it above)
                    print(f"⚠️ Stripe subscription is {subscription_status} - payment method not collected")
                    return Response(
                        {'error': 'Payment method was not collected. Please try again.'}, 
                        status=status.HTTP_402_PAYMENT_REQUIRED
                    )
                
                elif subscription_status in ['past_due', 'unpaid', 'canceled']:
                    # Payment failed or subscription canceled
                    print(f"⚠️ Stripe subscription is {subscription_status} - payment failed")
                    return Response(
                        {'error': 'Payment failed. Please check your payment method and try again.'}, 
                        status=status.HTTP_402_PAYMENT_REQUIRED
                    )
                
                else:
                    # Unknown status
                    print(f"⚠️ Unknown subscription status: {subscription_status}")
                    return Response(
                        {'error': f'Payment status unclear (status: {subscription_status}). Please contact support.'}, 
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                    
            except stripe.error.InvalidRequestError as e:
                error_message = str(e)
                error_code = getattr(e, 'code', None)
                print(f"❌ Stripe error querying subscription: {error_message}")
                print(f"❌ Error code: {error_code}")
                print(f"❌ Subscription ID attempted: {subscription_id}")
                
                # Check if subscription doesn't exist
                if 'No such subscription' in error_message or error_code == 'resource_missing':
                    return Response(
                        {
                            'error': 'Subscription not found in Stripe. The subscription may have been canceled or does not exist.',
                            'details': error_message,
                            'subscription_id': subscription_id
                        }, 
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                return Response(
                    {
                        'error': 'Could not verify payment status with Stripe. Please contact support.',
                        'details': error_message,
                        'error_code': error_code
                    }, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            except Exception as e:
                print(f"❌ Error querying Stripe: {e}")
                import traceback
                traceback.print_exc()
                return Response(
                    {'error': 'Failed to verify payment status. Please contact support.'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
        except Course.DoesNotExist:
            return Response(
                {'error': 'Course not found or not published'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Class.DoesNotExist:
            return Response(
                {'error': 'Selected class not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"❌ Error confirming enrollment: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': 'Failed to confirm enrollment', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _handle_one_time_payment_enrollment(self, request, course, class_id, payment_intent_id, pricing_type):
        """Handle enrollment confirmation for one-time payments (no subscription)"""
        try:
            from courses.models import Class
            from student.models import EnrolledCourse
            import time
            
            selected_class = get_object_or_404(Class, id=class_id)
            
            # Poll for payment intent status (max 15 seconds)
            max_wait_time = 15
            poll_interval = 0.5
            start_time = time.time()
            
            print(f"🔄 Polling for payment intent completion: {payment_intent_id}")
            
            while time.time() - start_time < max_wait_time:
                try:
                    # Check payment intent status directly from Stripe
                    get_stripe_client()
                    payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
                    
                    if payment_intent.status == 'succeeded':
                        # Check if enrollment was created by webhook
                        student_profile = getattr(request.user, 'student_profile', None)
                        if not student_profile:
                            return Response(
                                {'error': 'Student profile not found'}, 
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        
                        enrollment = EnrolledCourse.objects.filter(
                            student_profile=student_profile,
                            course=course
                        ).first()
                        
                        if enrollment:
                            print(f"✅ Enrollment completed: {enrollment.id}")
                            return Response({
                                'message': 'Payment successful and enrollment completed',
                                'enrollment_id': str(enrollment.id),
                                'is_trial': False,
                                'trial_end_date': None
                            }, status=status.HTTP_201_CREATED)
                        else:
                            # Payment succeeded but enrollment not created - create it now
                            print(f"🔄 Payment succeeded but enrollment not found - creating enrollment...")
                            enrollment = self._create_one_time_enrollment(
                                request.user, course, class_id, payment_intent_id, pricing_type
                            )
                            
                            if enrollment:
                                return Response({
                                    'message': 'Payment successful and enrollment created',
                                    'enrollment_id': str(enrollment.id),
                                    'is_trial': False,
                                    'trial_end_date': None
                                }, status=status.HTTP_201_CREATED)
                    
                    elif payment_intent.status in ['canceled', 'payment_failed']:
                        return Response(
                            {'error': f'Payment {payment_intent.status}. Please try again.'}, 
                            status=status.HTTP_402_PAYMENT_REQUIRED
                        )
                    
                    time.sleep(poll_interval)
                    
                except stripe.error.InvalidRequestError as e:
                    print(f"⚠️ Payment intent not found or error: {e}")
                    time.sleep(poll_interval)
                except Exception as e:
                    print(f"❌ Error during polling: {e}")
                    time.sleep(poll_interval)
            
            # Timeout - query Stripe directly
            print(f"⏰ Timeout: Checking payment intent status directly...")
            try:
                get_stripe_client()
                payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
                
                if payment_intent.status == 'succeeded':
                    # Create enrollment directly
                    enrollment = self._create_one_time_enrollment(
                        request.user, course, class_id, payment_intent_id, pricing_type
                    )
                    
                    if enrollment:
                        return Response({
                            'message': 'Payment verified and enrollment created',
                            'enrollment_id': str(enrollment.id),
                            'is_trial': False,
                            'trial_end_date': None,
                            'verified_via': 'stripe_direct_query'
                        }, status=status.HTTP_201_CREATED)
                    else:
                        return Response(
                            {'error': 'Payment verified but enrollment creation failed'}, 
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )
                else:
                    return Response(
                        {'error': f'Payment status: {payment_intent.status}. Please try again.'}, 
                        status=status.HTTP_402_PAYMENT_REQUIRED
                    )
            except Exception as e:
                print(f"❌ Error verifying payment: {e}")
                return Response(
                    {'error': 'Could not verify payment status. Please contact support.'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Exception as e:
            print(f"❌ Error handling one-time payment enrollment: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': 'Failed to confirm enrollment', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _create_one_time_enrollment(self, user, course, class_id, payment_intent_id, pricing_type):
        """Create enrollment for one-time payments (no subscription)"""
        try:
            from student.models import EnrolledCourse
            from courses.models import Class
            from django.db import transaction
            
            with transaction.atomic():
                # Get student profile
                student_profile = getattr(user, 'student_profile', None)
                if not student_profile:
                    print(f"❌ Student profile not found for user {user.id}")
                    return None
                
                # Check if enrollment already exists
                existing_enrollment = EnrolledCourse.objects.filter(
                    student_profile=student_profile,
                    course=course
                ).first()
                
                if existing_enrollment and existing_enrollment.status in ['active', 'completed']:
                    print(f"✅ Enrollment already exists: {existing_enrollment.id}")
                    return existing_enrollment
                
                # Get the selected class
                try:
                    selected_class = Class.objects.get(id=class_id)
                except Class.DoesNotExist:
                    print(f"❌ Class {class_id} not found")
                    return None
                
                # Get payment amount from Stripe
                get_stripe_client()
                payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
                amount_paid = payment_intent.amount / 100  # Convert from cents
                
                # Create enrollment
                enrollment = EnrolledCourse.objects.create(
                    student_profile=student_profile,
                    course=course,
                    status='active',
                    enrolled_by=user,
                    
                    # Payment information
                    payment_status='paid',
                    amount_paid=amount_paid,
                    payment_due_date=None,
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
                try:
                    if selected_class.student_count < selected_class.max_capacity:
                        selected_class.students.add(user)
                except Exception as e:
                    print(f"⚠️ Failed to add student to class: {e}")
                
                # Create Payment record
                try:
                    Payment.objects.create(
                        user=user,
                        course=course,
                        stripe_payment_intent_id=payment_intent_id,
                        amount=amount_paid,
                        currency=payment_intent.currency,
                        status='succeeded',
                        paid_at=timezone.now()
                    )
                except Exception as e:
                    print(f"⚠️ Failed to create payment record: {e}")
                
                print(f"✅ One-time enrollment created: {enrollment.id}")
                return enrollment
                
        except Exception as e:
            print(f"❌ Error creating one-time enrollment: {e}")
            import traceback
            traceback.print_exc()
            return None


class CancelIncompleteSubscriptionView(APIView):
    """
    Cancel an incomplete Stripe subscription (e.g., when user abandons enrollment flow)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id: str):
        print(f"🗑️ Canceling incomplete subscription for course: {course_id}")
        print(f"🗑️ Request data: {request.data}")
        
        try:
            get_stripe_client()
            
            subscription_id = request.data.get('subscription_id')
            if not subscription_id:
                return Response({'error': 'subscription_id is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            print(f"🗑️ Attempting to cancel subscription: {subscription_id}")
            
            # Cancel the subscription in Stripe
            try:
                canceled_subscription = stripe.Subscription.cancel(subscription_id)
                print(f"✅ Successfully canceled subscription: {canceled_subscription.id}")
                print(f"✅ Subscription status: {canceled_subscription.status}")
                
                # Delete the local subscriber record since it was incomplete
                try:
                    local_subscriber = Subscribers.objects.get(stripe_subscription_id=subscription_id)
                    local_subscriber.delete()
                    print(f"✅ Deleted local subscriber record: {local_subscriber.id}")
                except Subscribers.DoesNotExist:
                    print(f"ℹ️ No local subscriber record found for: {subscription_id}")
                except Exception as e:
                    print(f"⚠️ Could not delete local subscriber record: {e}")
                
                return Response({
                    'message': 'Subscription canceled successfully',
                    'subscription_id': canceled_subscription.id,
                    'status': canceled_subscription.status
                }, status=status.HTTP_200_OK)
                
            except stripe.error.InvalidRequestError as e:
                print(f"⚠️ Subscription not found or already canceled: {e}")
                # If subscription doesn't exist or is already canceled, that's fine
                return Response({
                    'message': 'Subscription was already canceled or does not exist',
                    'subscription_id': subscription_id
                }, status=status.HTTP_200_OK)
                
            except stripe.error.StripeError as e:
                print(f"❌ Stripe error canceling subscription: {e}")
                return Response({
                    'error': 'Failed to cancel subscription in Stripe',
                    'details': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        except Exception as e:
            print(f"❌ Error canceling subscription: {e}")
            return Response({
                'error': 'Failed to cancel subscription',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BillingDashboardView(APIView):
    """
    Get billing dashboard data for a user (subscriptions and payments)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Get user's active and trialing subscriptions only
            subscriptions = Subscribers.objects.filter(
                user=request.user,
                status__in=['active', 'trialing']
            ).select_related('course')
            
            # Get user's payments
            payments = Payment.objects.filter(user=request.user).select_related('course')
            
            # Format subscriptions data
            subscriptions_data = []
            for sub in subscriptions:
                print(f"🔍 BillingDashboard: Subscriber {sub.id} status: {sub.status}")
                print(f"🔍 BillingDashboard: Subscriber {sub.id} stripe_id: {sub.stripe_subscription_id}")
                print(f"🔍 BillingDashboard: Subscriber {sub.id} created_at: {sub.created_at}")
                # Calculate display information
                is_trial = sub.status == 'trialing'
                is_monthly = sub.subscription_type == 'monthly'
                is_one_time = sub.subscription_type == 'one_time'
                
                # Determine payment description - focus on next invoice, not payment type
                if is_trial:
                    # For trials, show when trial ends and what happens next
                    if sub.next_invoice_date and sub.next_invoice_amount:
                        payment_description = f"Next invoice: ${float(sub.next_invoice_amount):.2f} on {sub.next_invoice_date.strftime('%b %d, %Y')}"
                    else:
                        payment_description = f"Trial ends {sub.trial_end.strftime('%b %d, %Y') if sub.trial_end else 'N/A'}"
                elif is_monthly:
                    # For monthly, show next invoice
                    # Use current_period_end as fallback if next_invoice_date is not set
                    next_billing_date = sub.next_invoice_date
                    if not next_billing_date and sub.current_period_end:
                        next_billing_date = sub.current_period_end
                    
                    if next_billing_date and sub.next_invoice_amount:
                        payment_description = f"Next invoice: ${float(sub.next_invoice_amount):.2f} on {next_billing_date.strftime('%b %d, %Y')}"
                    elif next_billing_date:
                        amount = float(sub.amount) if sub.amount else 0
                        payment_description = f"Next invoice: ${amount:.2f} on {next_billing_date.strftime('%b %d, %Y')}" if amount > 0 else f"Next billing: {next_billing_date.strftime('%b %d, %Y')}"
                    else:
                        payment_description = f"Monthly installments of ${float(sub.amount):.2f}" if sub.amount else "Monthly installments"
                else:  # one_time
                    # For one-time, show the total amount
                    payment_description = f"Total amount: ${float(sub.amount):.2f}" if sub.amount else "One-time payment"
                
                # Next invoice information
                next_invoice_info = None
                if sub.next_invoice_date and sub.next_invoice_amount:
                    next_invoice_info = {
                        'date': sub.next_invoice_date.strftime('%b %d, %Y'),
                        'amount': float(sub.next_invoice_amount),
                        'formatted': f"${float(sub.next_invoice_amount):.2f} on {sub.next_invoice_date.strftime('%b %d, %Y')}"
                    }
                
                subscriptions_data.append({
                    'id': sub.id,
                    'course_title': sub.course.title,
                    'course_id': str(sub.course.id),
                    'status': sub.status,
                    'subscription_type': sub.subscription_type,
                    'billing_interval': sub.billing_interval,
                    'amount': float(sub.amount) if sub.amount else 0,
                    'payment_description': payment_description,
                    'is_trial': is_trial,
                    'is_monthly': is_monthly,
                    'is_one_time': is_one_time,
                    'next_invoice_date': sub.next_invoice_date.isoformat() if sub.next_invoice_date else None,
                    'next_invoice_amount': float(sub.next_invoice_amount) if sub.next_invoice_amount else 0,
                    'next_invoice_info': next_invoice_info,
                    'trial_end': sub.trial_end.isoformat() if sub.trial_end else None,
                    'trial_end_formatted': sub.trial_end.strftime('%b %d, %Y') if sub.trial_end else None,
                    'current_period_start': sub.current_period_start.isoformat() if sub.current_period_start else None,
                    'current_period_end': sub.current_period_end.isoformat() if sub.current_period_end else None,
                    'cancel_at': sub.cancel_at.isoformat() if sub.cancel_at else None,
                    'created_at': sub.created_at.isoformat(),
                    'updated_at': sub.updated_at.isoformat(),
                })
            
            # Format payments data
            payments_data = []
            for payment in payments:
                payments_data.append({
                    'id': payment.id,
                    'course_title': payment.course.title if payment.course else 'Unknown Course',
                    'course_id': str(payment.course.id) if payment.course else None,
                    'amount': float(payment.amount),
                    'currency': payment.currency,
                    'status': payment.status,
                    'paid_at': payment.paid_at.isoformat() if payment.paid_at else None,
                    'created_at': payment.created_at.isoformat(),
                    'stripe_invoice_id': payment.stripe_invoice_id,
                })
            
            return Response({
                'subscriptions': subscriptions_data,
                'payments': payments_data,
                'total_subscriptions': len(subscriptions_data),
                'total_payments': len(payments_data),
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Error fetching billing dashboard: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': 'Failed to fetch billing data', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DownloadInvoiceView(APIView):
    """
    Download invoice PDF from Stripe for authenticated users
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, payment_id: int):
        try:
            # Initialize Stripe client
            get_stripe_client()
            
            # Get payment record and validate ownership
            payment = Payment.objects.get(id=payment_id, user=request.user)
            
            if not payment.stripe_invoice_id:
                return Response(
                    {'error': 'No invoice available for this payment'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get invoice from Stripe
            stripe_invoice = stripe.Invoice.retrieve(payment.stripe_invoice_id)
            invoice_pdf_url = stripe_invoice.get('invoice_pdf')
            
            if not invoice_pdf_url:
                return Response(
                    {'error': 'PDF not available from Stripe'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Stream PDF content from Stripe
            import requests
            pdf_response = requests.get(invoice_pdf_url, stream=True)
            
            if pdf_response.status_code != 200:
                print(f"❌ Failed to fetch PDF from Stripe: {pdf_response.status_code}")
                return Response(
                    {'error': 'Failed to fetch PDF from Stripe'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Create Django response with PDF content
            response = HttpResponse(
                pdf_response.content,
                content_type='application/pdf'
            )
            response['Content-Disposition'] = f'attachment; filename="invoice_{payment_id}.pdf"'
            response['Cache-Control'] = 'no-cache'
            
            return response
            
        except Payment.DoesNotExist:
            print(f"❌ Payment {payment_id} not found for user {request.user.id}")
            return Response(
                {'error': 'Payment not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"❌ Error downloading invoice: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': 'Failed to download invoice'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CancelCourseView(APIView):
    """
    Cancel course subscription and remove student from course
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, subscription_id: int):
        try:
            print(f"🔍 CancelCourseView: Received subscription_id: {subscription_id} (type: {type(subscription_id)})")
            
            # Get subscription and validate ownership
            subscriber = Subscribers.objects.get(
                id=subscription_id,
                user=request.user
            )
            
            # Get cancellation reason from request
            reason = request.data.get('reason', 'No reason provided')
            
            # Cancel Stripe subscription
            try:
                stripe.Subscription.cancel(subscriber.stripe_subscription_id)
                print(f"✅ Stripe subscription {subscriber.stripe_subscription_id} cancelled successfully")
            except Exception as e:
                print(f"❌ Failed to cancel Stripe subscription: {e}")
                # If Stripe fails, we still cancel locally to maintain consistency
                # User will be removed from course regardless of Stripe status
            
            # Update local subscription status
            subscriber.status = 'canceled'
            subscriber.canceled_at = timezone.now()
            subscriber.save()
            
            # Remove from enrolled courses
            try:
                enrolled_course = EnrolledCourse.objects.get(
                    student_profile__user=request.user,
                    course=subscriber.course
                )
                enrolled_course.delete()
                print(f"✅ Removed user {request.user.id} from course {subscriber.course.id}")
            except EnrolledCourse.DoesNotExist:
                print(f"⚠️ No enrolled course found for user {request.user.id} and course {subscriber.course.id}")
            
            return Response({
                'message': 'Course cancelled successfully',
                'cancelled_at': subscriber.canceled_at.isoformat(),
                'reason': reason
            })
            
        except Subscribers.DoesNotExist:
            print(f"❌ Subscription {subscription_id} not found for user {request.user.id}")
            return Response(
                {'error': 'Subscription not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"❌ Error cancelling course: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': 'Failed to cancel course'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CreateCustomerPortalSessionView(APIView):
    """
    Create Stripe Customer Portal session for payment method management
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # Initialize Stripe
            get_stripe_client()
            
            # Ensure customer exists in current environment (auto-migrate if needed)
            stripe_customer_id = ensure_stripe_customer_in_current_environment(request.user)
            
            # Create Stripe Customer Portal session
            # Get Stripe billing redirect URL from environment variable
            billing_redirect_url = os.getenv('STRIPE_BILLING_REDIRECT_URL', 'http://localhost:8080/billing-success')
            
            if not billing_redirect_url:
                return Response(
                    {'error': 'Billing redirect URL not configured'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            session = stripe.billing_portal.Session.create(
                customer=stripe_customer_id,
                return_url=billing_redirect_url,
                # Optional: specify a configuration ID if you have one
                # configuration='bpc_xxxxxxxxxxxxx'
            )
            
            return Response({
                'url': session.url
            })
            
        except CustomerAccount.DoesNotExist:
            return Response(
                {'error': 'Customer account not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': 'Failed to create billing portal session'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
