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
            
            # Log webhook event
            WebhookEvent.objects.create(
                stripe_event_id=event['id'],
                event_type=event['type'],
                processed=False,
                data=event['data']
            )
            
            # Handle the event
            if event['type'] == 'checkout.session.completed':
                self._handle_checkout_completed(event['data']['object'])
            elif event['type'] == 'customer.subscription.created':
                self._handle_subscription_created(event['data']['object'])
            elif event['type'] == 'customer.subscription.updated':
                self._handle_subscription_updated(event['data']['object'])
            elif event['type'] == 'customer.subscription.deleted':
                self._handle_subscription_deleted(event['data']['object'])
            elif event['type'] == 'invoice.payment_succeeded':
                self._handle_payment_succeeded(event['data']['object'])
            elif event['type'] == 'invoice.payment_failed':
                self._handle_payment_failed(event['data']['object'])
            
            return HttpResponse("Webhook processed successfully", status=200)
            
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
            sub.status = subscription['status']
            sub.current_period_start = timezone.datetime.fromtimestamp(
                subscription['current_period_start'], tz=timezone.utc
            )
            sub.current_period_end = timezone.datetime.fromtimestamp(
                subscription['current_period_end'], tz=timezone.utc
            )
            sub.cancel_at = None
            if subscription.get('cancel_at'):
                sub.cancel_at = timezone.datetime.fromtimestamp(
                    subscription['cancel_at'], tz=timezone.utc
                )
            sub.save()
        except Subscription.DoesNotExist:
            pass
        except Exception as e:
            print(f"Error handling subscription updated: {e}")
    
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
                except Subscription.DoesNotExist:
                    pass
        except Exception as e:
            print(f"Error handling payment failed: {e}")
