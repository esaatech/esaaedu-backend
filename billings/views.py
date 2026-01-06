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
        # Get existing prices from database
        existing_prices = BillingPrice.objects.filter(
            product=billing_product,
            is_active=True
        )
        
        one_time_price_obj = existing_prices.filter(billing_period='one_time').first()
        monthly_price_obj = existing_prices.filter(billing_period='monthly').first()
        
        # Check and migrate one-time price
        one_time_price_id = None
        if one_time_price_obj and one_time_price_obj.stripe_price_id:
            try:
                stripe.Price.retrieve(one_time_price_obj.stripe_price_id)
                one_time_price_id = one_time_price_obj.stripe_price_id
                print(f"✅ One-time price {one_time_price_id} exists in current environment")
            except stripe.error.InvalidRequestError as e:
                if 'No such price' in str(e) or getattr(e, 'code', '') == 'resource_missing':
                    print(f"⚠️ One-time price {one_time_price_obj.stripe_price_id} not found - creating new one")
                    one_time_price_obj = None  # Will create new below
                else:
                    raise e
        
        if not one_time_price_id:
            # Create new one-time price
            print(f"🔄 Creating new one-time price in current environment")
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
            
            # Update or create BillingPrice record
            if one_time_price_obj:
                one_time_price_obj.stripe_price_id = one_time_price_id
                one_time_price_obj.unit_amount = prices['one_time_price']
                one_time_price_obj.is_active = True
                one_time_price_obj.save(update_fields=['stripe_price_id', 'unit_amount', 'is_active'])
            else:
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
        if prices['total_months'] > 1:
            if monthly_price_obj and monthly_price_obj.stripe_price_id:
                try:
                    stripe.Price.retrieve(monthly_price_obj.stripe_price_id)
                    monthly_price_id = monthly_price_obj.stripe_price_id
                    print(f"✅ Monthly price {monthly_price_id} exists in current environment")
                except stripe.error.InvalidRequestError as e:
                    if 'No such price' in str(e) or getattr(e, 'code', '') == 'resource_missing':
                        print(f"⚠️ Monthly price {monthly_price_obj.stripe_price_id} not found - creating new one")
                        monthly_price_obj = None  # Will create new below
                    else:
                        raise e
            
            if not monthly_price_id:
                # Create new monthly price
                print(f"🔄 Creating new monthly price in current environment")
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
                
                # Update or create BillingPrice record
                if monthly_price_obj:
                    monthly_price_obj.stripe_price_id = monthly_price_id
                    monthly_price_obj.unit_amount = prices['monthly_price']
                    monthly_price_obj.is_active = True
                    monthly_price_obj.save(update_fields=['stripe_price_id', 'unit_amount', 'is_active'])
                else:
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
                if s['next_invoice_date'] and s['next_invoice_amount']:
                    payment_description = f"Next invoice: ${float(s['next_invoice_amount']):.2f} on {s['next_invoice_date'].strftime('%b %d, %Y')}"
                else:
                    amount = float(s['amount']) if s['amount'] else 0
                    payment_description = f"Monthly installments of ${amount:.2f}" if amount > 0 else "Monthly installments"
            else:  # one_time
                # For one-time, show the total amount
                amount = float(s['amount']) if s['amount'] else 0
                payment_description = f"Total amount: ${amount:.2f}" if amount > 0 else "One-time payment"
            
            # Next invoice information
            next_invoice_info = None
            if s['next_invoice_date'] and s['next_invoice_amount']:
                next_invoice_info = {
                    'date': s['next_invoice_date'].strftime('%b %d, %Y'),
                    'amount': float(s['next_invoice_amount']),
                    'formatted': f"${float(s['next_invoice_amount']):.2f} on {s['next_invoice_date'].strftime('%b %d, %Y')}"
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
            
            # Find the most recent subscription for this customer
            subscription_id = None
            if customer_id:
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
                        print(f"✅ Found subscription {subscription_id} for customer {customer_id}")
                    else:
                        print(f"⚠️ No incomplete subscription found for customer {customer_id}")
                except CustomerAccount.DoesNotExist:
                    print(f"⚠️ Customer account not found for {customer_id}")
            if subscription_id:
                try:
                    # Update Subscribers table
                    subscriber = Subscribers.objects.get(stripe_subscription_id=subscription_id)
                    subscriber.status = 'trialing'  # Update to trialing when payment succeeds
                    # Keep subscription_type as 'trial' - only update to monthly/one_time after trial ends
                    subscriber.save()
                    print(f"✅ Updated subscriber {subscriber.id} to trialing status")
                    
                    # CRITICAL: Ensure enrollment is created when payment succeeds
                    print(f"🎓 Webhook: Ensuring enrollment is created for subscription {subscription_id}")
                    try:
                        # Get the subscription from Stripe to get metadata
                        stripe_subscription = stripe.Subscription.retrieve(subscription_id)
                        metadata = stripe_subscription.get('metadata', {})
                        course_id = metadata.get('course_id')
                        class_id = metadata.get('class_id')
                        pricing_type = metadata.get('pricing_type', 'one_time')
                        
                        print(f"🔍 Webhook: Processing subscription {subscription_id} - Course: {course_id}, Class: {class_id}")
                        
                        if course_id and class_id:
                            from courses.models import Course
                            course = Course.objects.get(id=course_id)
                            user = subscriber.user
                            is_trial = True  # Payment succeeded means trial started
                            
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
                    
                    # Create payment record when setup succeeds (after enrollment)
                    try:
                        setup_intent_id = setup_intent.get('id')
                        self._create_payment_record_from_setup(subscription_id, setup_intent_id)
                        print(f"✅ Payment record created for setup intent {setup_intent_id}")
                    except Exception as e:
                        print(f"❌ Error creating payment record: {e}")
                        import traceback
                        traceback.print_exc()
                    
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
        """Handle successful payment - updates existing payment record"""
        pass
       
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
            
            # Debug: Find any payment records associated with this payment intent
            payments_to_delete = Payment.objects.filter(stripe_payment_intent_id=payment_intent_id)
            print(f"🔍 Found {payments_to_delete.count()} payment records for canceled payment intent")
                
        except Exception as e:
            print(f"❌ Error handling payment intent canceled: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_setup_intent_canceled(self, setup_intent):
        """Handle when user cancels setup intent for subscription"""
        try:
            setup_intent_id = setup_intent['id']
            print(f"🚫 Setup intent canceled: {setup_intent_id}")
            
            # Debug: Find any payment records associated with this setup intent
            payments_to_delete = Payment.objects.filter(stripe_payment_intent_id=setup_intent_id)
            print(f"🔍 Found {payments_to_delete.count()} payment records for canceled setup intent")
                
        except Exception as e:
            print(f"❌ Error handling setup intent canceled: {e}")
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
            
            # Get or create customer
            customer_account, created = CustomerAccount.objects.get_or_create(
                user=request.user
            )
            
            if not customer_account.stripe_customer_id:
                # Create Stripe customer
                stripe_customer = stripe.Customer.create(
                    email=request.user.email,
                    name=f"{request.user.first_name} {request.user.last_name}".strip() or request.user.email,
                    metadata={
                        'user_id': str(request.user.id),
                        'course_id': str(course.id),
                    }
                )
                customer_account.stripe_customer_id = stripe_customer.id
                customer_account.save()
            
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
                trial_days = trial_settings['days'] if (request.data.get('trial_period') and trial_settings['enabled']) else 0
                print(f"🚀 Trial period: {trial_days} days")
                
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
                            subscription = stripe.Subscription.create(
                                customer=customer_account.stripe_customer_id,
                                items=[{'price': stripe_price_id}],
                                # Add trial when requested so Stripe auto-manages conversion after trial
                                trial_period_days=trial_days if request.data.get('trial_period') else None,
                                cancel_at=int(cancel_at.timestamp()),  # Cancel after specified number of monthly payments
                                payment_behavior='default_incomplete',
                                payment_settings={'save_default_payment_method': 'on_subscription'},
                                expand=['latest_invoice.payment_intent', 'pending_setup_intent'],
                                metadata={
                                    'course_id': str(course.id),
                                    'course_title': course.title,
                                    'user_id': str(request.user.id),
                                    'user_email': request.user.email,
                                    'pricing_type': pricing_type,  # Store the original pricing choice
                                    'trial_period': str(bool(request.data.get('trial_period'))).lower(),
                                    'class_id': str(request.data.get('class_id', '')),
                                    'student_profile_id': str(getattr(request.user, 'student_profile', {}).id if hasattr(request.user, 'student_profile') and request.user.student_profile else '')
                                }
                            )
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
                intent_type = 'payment'
                client_secret = None
                payment_intent_id = None
                setup_intent_id = None
                if getattr(subscription, 'latest_invoice', None) and getattr(subscription.latest_invoice, 'payment_intent', None):
                    payment_intent = subscription.latest_invoice.payment_intent
                    client_secret = payment_intent.client_secret
                    payment_intent_id = payment_intent.id
                    print(f"💳 Using payment intent from latest_invoice: {payment_intent_id}")
                elif getattr(subscription, 'pending_setup_intent', None):
                    setup_intent = subscription.pending_setup_intent
                    client_secret = setup_intent.client_secret
                    setup_intent_id = setup_intent.id
                    intent_type = 'setup'
                    print(f"🔧 Using setup intent: {setup_intent_id}")
                else:
                    print(f"❌ No payment or setup intent available for subscription")
                    raise Exception('No payment or setup intent available for subscription')
                
            else:
                amount = int(pricing_options['one_time']['amount'] * 100)
                print(f"💳 Creating one-time payment: ${pricing_options['one_time']['amount']}")
                
                if request.data.get('trial_period'):
                    # For one-time payments with trial, create a subscription that will charge once and then cancel
                    print(f"🔄 Creating one-time subscription with trial for: ${pricing_options['one_time']['amount']}")
                    
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
                        
                        # Get trial period settings
                        trial_settings = get_trial_period_settings()
                        trial_days = trial_settings['days'] if trial_settings['enabled'] else 0
                        
                        # Calculate when to cancel: trial end + 1 billing cycle (1 month)
                        trial_end = datetime.datetime.now(dt_timezone.utc) + datetime.timedelta(days=trial_days)
                        cancel_at = trial_end + datetime.timedelta(days=30)  # 1 month after trial ends
                        print(f"🗓️ Trial ends: {trial_end.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                        print(f"🗓️ Subscription will cancel: {cancel_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                        
                        subscription = stripe.Subscription.create(
                            customer=customer_account.stripe_customer_id,
                            items=[{'price': stripe_price_id}],
                            trial_period_days=trial_days,
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
                            intent_type = 'payment'
                            client_secret = None
                            payment_intent_id = None
                            setup_intent_id = None
                            if getattr(subscription, 'latest_invoice', None) and getattr(subscription.latest_invoice, 'payment_intent', None):
                                payment_intent = subscription.latest_invoice.payment_intent
                                client_secret = payment_intent.client_secret
                                payment_intent_id = payment_intent.id
                                print(f"💳 Using payment intent from latest_invoice: {payment_intent_id}")
                            elif getattr(subscription, 'pending_setup_intent', None):
                                setup_intent = subscription.pending_setup_intent
                                client_secret = setup_intent.client_secret
                                setup_intent_id = setup_intent.id
                                intent_type = 'setup'
                                print(f"🔧 Using setup intent: {setup_intent_id}")
                            else:
                                print(f"❌ No payment or setup intent available for one-time subscription")
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
                        customer=customer_account.stripe_customer_id,
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
                'amount': amount,
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
            is_trial = request.data.get('trial_period', False)
            
            if not class_id:
                return Response(
                    {'error': 'Class ID is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not subscription_id:
                return Response(
                    {'error': 'Subscription ID is required for enrollment confirmation'}, 
                    status=status.HTTP_400_BAD_REQUEST
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
            
            # Timeout reached
            print(f"⏰ Timeout: Webhook did not complete enrollment within {max_wait_time} seconds")
            return Response(
                {'error': 'Enrollment confirmation timed out. Please check your enrollment status.'}, 
                status=status.HTTP_408_REQUEST_TIMEOUT
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
                    if sub.next_invoice_date and sub.next_invoice_amount:
                        payment_description = f"Next invoice: ${float(sub.next_invoice_amount):.2f} on {sub.next_invoice_date.strftime('%b %d, %Y')}"
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
            # Get customer account
            customer_account = CustomerAccount.objects.get(user=request.user)
            
            # Initialize Stripe
            get_stripe_client()
            
            # Create Stripe Customer Portal session
            # Get Stripe billing redirect URL from environment variable
            billing_redirect_url = os.getenv('STRIPE_BILLING_REDIRECT_URL', 'http://localhost:8080/billing-success')
            
            if not billing_redirect_url:
                return Response(
                    {'error': 'Billing redirect URL not configured'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            session = stripe.billing_portal.Session.create(
                customer=customer_account.stripe_customer_id,
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
