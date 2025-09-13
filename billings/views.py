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

from .models import BillingProduct, BillingPrice, CustomerAccount, Subscription, WebhookEvent
from courses.models import Course


def get_stripe_client() -> None:
    api_key = os.environ.get('STRIPE_SECRET_KEY') or getattr(settings, 'STRIPE_SECRET_KEY', None)
    if not api_key:
        raise RuntimeError("Stripe secret key not configured (STRIPE_SECRET_KEY)")
    stripe.api_key = api_key


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
                # Subscription with 14-day trial, card collected
                session = stripe.checkout.Session.create(
                    mode='subscription',
                    customer=customer.stripe_customer_id,
                    line_items=[{"price": price.stripe_price_id, "quantity": 1}],
                    subscription_data={"trial_period_days": 14},
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
        subs = Subscription.objects.filter(user=request.user).values(
            'id', 'course_id', 'stripe_subscription_id', 'stripe_price_id', 'status',
            'current_period_start', 'current_period_end', 'cancel_at'
        )
        # Convert datetimes to ISO
        data = []
        for s in subs:
            data.append({
                **s,
                'current_period_start': s['current_period_start'].isoformat() if s['current_period_start'] else None,
                'current_period_end': s['current_period_end'].isoformat() if s['current_period_end'] else None,
                'cancel_at': s['cancel_at'].isoformat() if s['cancel_at'] else None,
            })
        return Response(data)


class CancelSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, subscription_id: str):
        try:
            get_stripe_client()
            sub = get_object_or_404(Subscription, id=subscription_id, user=request.user)
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
                else:
                    print(f"ℹ️ Unhandled event type: {event['type']}")
                
                # Log successful processing
                WebhookEvent.objects.create(
                    stripe_event_id=event_id,
                    type=event['type'],
                    payload=event['data']
                )
                
                print(f"✅ Successfully processed webhook: {event['type']}")
                return HttpResponse("Webhook processed successfully", status=200)
                
            except Exception as handler_error:
                print(f"❌ Error processing webhook {event['type']}: {handler_error}")
                import traceback
                traceback.print_exc()
                raise handler_error
            
        except Exception as e:
            return HttpResponse(f"Webhook error: {str(e)}", status=500)
    
    def _handle_checkout_completed(self, session):
        """Handle successful checkout session"""
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
                        Subscription.objects.create(
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
    
    def _handle_subscription_created(self, subscription):
        """Handle subscription creation"""
        # This is handled in checkout_completed for our use case
        pass
    
    def _handle_subscription_updated(self, subscription):
        """Handle subscription updates"""
        try:
            sub = Subscription.objects.get(stripe_subscription_id=subscription['id'])
            old_status = sub.status
            sub.status = subscription['status']
            
            # Handle period dates safely (like we did in enrollment)
            from datetime import datetime, timedelta
            
            if subscription.get('current_period_start'):
                sub.current_period_start = datetime.fromtimestamp(
                    subscription['current_period_start'], tz=timezone.utc
                )
            elif subscription.get('trial_start'):
                sub.current_period_start = datetime.fromtimestamp(
                    subscription['trial_start'], tz=timezone.utc
                )
            
            if subscription.get('current_period_end'):
                sub.current_period_end = datetime.fromtimestamp(
                    subscription['current_period_end'], tz=timezone.utc
                )
            elif subscription.get('trial_end'):
                sub.current_period_end = datetime.fromtimestamp(
                    subscription['trial_end'], tz=timezone.utc
                )
            
            sub.cancel_at = None
            if subscription.get('cancel_at'):
                sub.cancel_at = datetime.fromtimestamp(
                    subscription['cancel_at'], tz=timezone.utc
                )
                
            if subscription.get('canceled_at'):
                sub.canceled_at = datetime.fromtimestamp(
                    subscription['canceled_at'], tz=timezone.utc
                )
            
            sub.save()
            
            print(f"✅ Updated subscription {subscription['id']}: {old_status} → {sub.status}")
            
        except Subscription.DoesNotExist:
            print(f"⚠️ Subscription {subscription['id']} not found for update")
        except Exception as e:
            print(f"❌ Error handling subscription updated: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_subscription_deleted(self, subscription):
        """Handle subscription cancellation"""
        try:
            sub = Subscription.objects.get(stripe_subscription_id=subscription['id'])
            sub.status = 'canceled'
            sub.save()
        except Subscription.DoesNotExist:
            pass
        except Exception as e:
            print(f"Error handling subscription deleted: {e}")
    
    def _handle_payment_succeeded(self, invoice):
        """Handle successful payment"""
        try:
            # Update subscription status if needed
            subscription_id = invoice.get('subscription')
            if subscription_id:
                try:
                    sub = Subscription.objects.get(stripe_subscription_id=subscription_id)
                    sub.status = 'active'
                    sub.save()
                except Subscription.DoesNotExist:
                    pass
        except Exception as e:
            print(f"Error handling payment succeeded: {e}")
    
    def _handle_payment_failed(self, invoice):
        """Handle failed payment"""
        try:
            subscription_id = invoice.get('subscription')
            if subscription_id:
                try:
                    sub = Subscription.objects.get(stripe_subscription_id=subscription_id)
                    sub.status = 'past_due'
                    sub.save()
                    print(f"✅ Updated subscription {subscription_id} to past_due")
                except Subscription.DoesNotExist:
                    print(f"⚠️ Subscription {subscription_id} not found for failed payment")
        except Exception as e:
            print(f"❌ Error handling payment failed: {e}")
    
    def _handle_trial_ending(self, subscription):
        """Handle trial ending notification"""
        try:
            sub = Subscription.objects.get(stripe_subscription_id=subscription['id'])
            print(f"⏰ Trial ending soon for subscription {subscription['id']}")
            print(f"📧 TODO: Send trial ending email to user {sub.user.email}")
            # Here you could send an email notification to the user
        except Subscription.DoesNotExist:
            print(f"⚠️ Subscription {subscription['id']} not found for trial ending")
        except Exception as e:
            print(f"❌ Error handling trial ending: {e}")


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
            from .models import Subscription
            existing_subs = Subscription.objects.filter(
                user=request.user,
                course_id=course_id,
                status__in=['active', 'trialing', 'incomplete', 'incomplete_expired', 'past_due']
            )
            print(f"🔍 Found {existing_subs.count()} existing subscriptions for this user/course")
            for sub in existing_subs:
                print(f"  - Subscription {sub.stripe_subscription_id}: status={sub.status}, created={sub.created_at}")
        except Exception as e:
            print(f"⚠️ Error checking existing subscriptions: {e}")
        
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
                # Get pricing options from billing prices
                one_time_price = BillingPrice.objects.filter(
                    product=billing_product, billing_period='one_time'
                ).first()
                monthly_price = BillingPrice.objects.filter(
                    product=billing_product, billing_period='monthly'
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
                
                # For monthly payments, create a subscription instead of one-time payment
                # First, create or get a price in Stripe
                try:
                    billing_product = BillingProduct.objects.get(course=course)
                    monthly_price = BillingPrice.objects.get(
                        product=billing_product, 
                        billing_period='monthly'
                    )
                    stripe_price_id = monthly_price.stripe_price_id
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
                print(f"🚀 About to create Stripe subscription with price_id: {stripe_price_id}")
                print(f"🚀 Customer: {customer_account.stripe_customer_id}")
                print(f"🚀 Trial period: {14 if request.data.get('trial_period') else None} days")
                
                try:
                    # Calculate when to cancel the subscription after all monthly payments
                    import datetime
                    from datetime import timezone
                    
                    trial_days = 14 if request.data.get('trial_period') else 0
                    # Cancel after trial + (total_months * 30 days per month)
                    cancel_at = datetime.datetime.now(timezone.utc) + datetime.timedelta(
                        days=trial_days + (total_months * 30)
                    )
                    print(f"🗓️ Monthly subscription will cancel: {cancel_at.strftime('%Y-%m-%d %H:%M:%S UTC')} (after {total_months} payments)")
                    
                    subscription = stripe.Subscription.create(
                    customer=customer_account.stripe_customer_id,
                    items=[{'price': stripe_price_id}],
                    # Add trial when requested so Stripe auto-manages conversion after trial
                    trial_period_days=14 if request.data.get('trial_period') else None,
                    cancel_at=int(cancel_at.timestamp()),  # Cancel after specified number of monthly payments
                    payment_behavior='default_incomplete',
                    payment_settings={'save_default_payment_method': 'on_subscription'},
                    expand=['latest_invoice.payment_intent', 'pending_setup_intent'],
                    metadata={
                        'course_id': str(course.id),
                        'course_title': course.title,
                        'user_id': str(request.user.id),
                        'user_email': request.user.email,
                        'pricing_type': 'monthly',
                        'trial_period': str(bool(request.data.get('trial_period'))).lower()
                    }
                    )
                    print(f"✅ Stripe subscription created: {subscription.id}")
                    print(f"✅ Subscription status: {subscription.status}")
                    print(f"✅ Has latest_invoice: {bool(getattr(subscription, 'latest_invoice', None))}")
                    print(f"✅ Has pending_setup_intent: {bool(getattr(subscription, 'pending_setup_intent', None))}")
                    
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
                
                # For trialing subscriptions, Stripe provides a pending_setup_intent for PM collection
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
                        from datetime import timezone
                        
                        # Calculate when to cancel: trial end + 1 billing cycle (1 month)
                        trial_end = datetime.datetime.now(timezone.utc) + datetime.timedelta(days=14)
                        cancel_at = trial_end + datetime.timedelta(days=30)  # 1 month after trial ends
                        print(f"🗓️ Trial ends: {trial_end.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                        print(f"🗓️ Subscription will cancel: {cancel_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                        
                        subscription = stripe.Subscription.create(
                            customer=customer_account.stripe_customer_id,
                            items=[{'price': stripe_price_id}],
                            trial_period_days=14,
                            cancel_at=int(cancel_at.timestamp()),  # Cancel after first payment
                            payment_behavior='default_incomplete',
                            payment_settings={'save_default_payment_method': 'on_subscription'},
                            expand=['latest_invoice.payment_intent', 'pending_setup_intent'],
                            metadata={
                                'course_id': str(course.id),
                                'course_title': course.title,
                                'user_id': str(request.user.id),
                                'user_email': request.user.email,
                                'pricing_type': 'one_time_trial',
                                'trial_period': 'true'
                            }
                        )
                        print(f"✅ One-time trial subscription created: {subscription.id}")
                        print(f"✅ Subscription status: {subscription.status}")
                        
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
                            
                    except stripe.error.StripeError as e:
                        print(f"❌ Stripe error creating one-time trial subscription: {e}")
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
    Confirm successful payment and create enrollment (handles both trial and paid)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id: str):
        print(f"🎓 ConfirmEnrollmentView called with course_id: {course_id}")
        print(f"🎓 Request data: {request.data}")
        
        try:
            # Get course and class
            course = get_object_or_404(Course, id=course_id, status='published')
            class_id = request.data.get('class_id')
            payment_intent_id = request.data.get('payment_intent_id')
            pricing_type = request.data.get('pricing_type', 'one_time')
            is_trial = request.data.get('trial_period', False)
            
            if not class_id:
                return Response(
                    {'error': 'Class ID is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get student profile
            student_profile = getattr(request.user, 'student_profile', None)
            if not student_profile:
                return Response(
                    {'error': 'Student profile not found. Please complete your profile setup.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get the class
            from courses.models import Class
            selected_class = get_object_or_404(Class, id=class_id)
            
            # Check if already enrolled
            from student.models import EnrolledCourse
            existing_enrollment = EnrolledCourse.objects.filter(
                student_profile=student_profile,
                course=course
            ).first()
            
            if existing_enrollment:
                if existing_enrollment.status in ['active', 'completed']:
                    return Response(
                        {'message': 'Already enrolled in this course'}, 
                        status=status.HTTP_200_OK
                    )
                else:
                    # Reactivate dropped/paused enrollment
                    existing_enrollment.status = 'active'
                    existing_enrollment.save()
                    return Response({
                        'message': 'Enrollment reactivated',
                        'enrollment_id': str(existing_enrollment.id)
                    }, status=status.HTTP_200_OK)
            
            # Calculate payment details based on trial vs paid
            if is_trial:
                print("💫 Creating TRIAL enrollment")
                from datetime import timedelta
                trial_end_date = timezone.now().date() + timedelta(days=14)
                payment_status = 'free'
                amount_paid = 0
                payment_due_date = trial_end_date
            else:
                print("💳 Creating PAID enrollment")
                # Paid enrollment - get actual pricing
                try:
                    billing_product = BillingProduct.objects.get(course=course)
                    if pricing_type == 'monthly':
                        monthly_price = BillingPrice.objects.filter(
                            product=billing_product, billing_period='monthly'
                        ).first()
                        amount_paid = float(monthly_price.unit_amount) / 100 if monthly_price else float(course.price) * 1.15
                    else:
                        one_time_price = BillingPrice.objects.filter(
                            product=billing_product, billing_period='one_time'
                        ).first()
                        amount_paid = float(one_time_price.unit_amount) / 100 if one_time_price else float(course.price)
                except BillingProduct.DoesNotExist:
                    amount_paid = float(course.price) * 1.15 if pricing_type == 'monthly' else float(course.price)
                
                payment_status = 'paid'
                payment_due_date = None
            
            # Create enrollment and subscription atomically
            with transaction.atomic():
                # Create enrollment with proper fields
                enrollment = EnrolledCourse.objects.create(
                    student_profile=student_profile,
                    course=course,
                    status='active',
                    enrolled_by=request.user,
                    
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
                        selected_class.students.add(request.user)
                        print(f"✅ Added student to class: {selected_class.name}")
                    else:
                        print(f"⚠️ Class {selected_class.name} is full, student not added to class")
                except Exception as e:
                    print(f"⚠️ Failed to add student to class: {e}")
                
                # Create subscription record for both trial and paid subscriptions
                subscription_id = request.data.get('subscription_id')
                if subscription_id:
                    print(f"🔄 Creating local subscription record for: {subscription_id}")
                    try:
                        # Get the Stripe subscription details to populate our local record
                        stripe_subscription = stripe.Subscription.retrieve(subscription_id)
                        
                        print(f"🔍 Stripe subscription data: {stripe_subscription}")
                        
                        # Calculate period dates (handle trial vs active subscriptions)
                        from datetime import datetime
                        
                        # For trial subscriptions, current_period_start/end might not exist
                        # Use trial_start/trial_end instead
                        if stripe_subscription.get('current_period_start'):
                            current_period_start = datetime.fromtimestamp(
                                stripe_subscription['current_period_start'], tz=timezone.utc
                            )
                        elif stripe_subscription.get('trial_start'):
                            current_period_start = datetime.fromtimestamp(
                                stripe_subscription['trial_start'], tz=timezone.utc
                            )
                        else:
                            # Fallback to creation time
                            current_period_start = datetime.fromtimestamp(
                                stripe_subscription['created'], tz=timezone.utc
                            )
                        
                        if stripe_subscription.get('current_period_end'):
                            current_period_end = datetime.fromtimestamp(
                                stripe_subscription['current_period_end'], tz=timezone.utc
                            )
                        elif stripe_subscription.get('trial_end'):
                            current_period_end = datetime.fromtimestamp(
                                stripe_subscription['trial_end'], tz=timezone.utc
                            )
                        else:
                            # Fallback: 14 days from start for trials
                            from datetime import timedelta
                            current_period_end = current_period_start + timedelta(days=14)
                        
                        # Get the price ID from the subscription
                        stripe_price_id = stripe_subscription['items']['data'][0]['price']['id']
                        
                        # Handle cancel_at field safely
                        cancel_at = None
                        if stripe_subscription.get('cancel_at'):
                            cancel_at = datetime.fromtimestamp(
                                stripe_subscription['cancel_at'], tz=timezone.utc
                            )
                        
                        # Create local subscription record
                        subscription_record = Subscription.objects.create(
                            user=request.user,
                            course=course,
                            stripe_subscription_id=subscription_id,
                            stripe_price_id=stripe_price_id,
                            status=stripe_subscription['status'],
                            current_period_start=current_period_start,
                            current_period_end=current_period_end,
                            cancel_at=cancel_at,
                        )
                        
                        print(f"✅ Subscription record created: {subscription_record.id}")
                        print(f"✅ Status: {subscription_record.status}")
                        print(f"✅ Period: {current_period_start} to {current_period_end}")
                        
                    except Exception as e:
                        print(f"⚠️ Could not save subscription: {e}")
                        import traceback
                        traceback.print_exc()
                        # Re-raise to trigger transaction rollback
                        raise e
                else:
                    print("ℹ️ No subscription_id provided - this might be a one-time payment without trial")
            
            print(f"✅ Enrollment created: {enrollment.id} (Trial: {is_trial})")
            
            return Response({
                'message': f'{"Trial" if is_trial else "Paid"} enrollment successful',
                'enrollment_id': str(enrollment.id),
                'is_trial': is_trial,
                'trial_end_date': payment_due_date.isoformat() if payment_due_date else None
            }, status=status.HTTP_201_CREATED)
            
        except Course.DoesNotExist:
            return Response(
                {'error': 'Course not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(f"Error confirming enrollment: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': 'Failed to create enrollment', 'details': str(e)}, 
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
