"""
Stripe integration utilities for course creation
"""
import os
import stripe
from django.conf import settings
from django.utils import timezone
from billings.models import BillingProduct, BillingPrice
from .price_calculator import calculate_course_prices


def get_stripe_client():
    """Initialize Stripe client with API key"""
    api_key = os.environ.get('STRIPE_SECRET_KEY') or getattr(settings, 'STRIPE_SECRET_KEY', None)
    
    if not api_key:
        raise RuntimeError("Stripe secret key not configured (STRIPE_SECRET_KEY)")
    
    stripe.api_key = api_key
    return stripe


def create_stripe_product_for_course(course):
    """
    Create Stripe product and prices for a course
    
    Logic:
    - ≤ 1 month (4 weeks): Only one-time price
    - > 1 month: One-time price + monthly subscription
    """
    try:
        stripe_client = get_stripe_client()
        
        # Create Stripe Product
        product = stripe_client.Product.create(
            name=course.title,
            description=course.description,
            metadata={
                'course_id': str(course.id),
                'teacher_id': str(course.teacher.id),
                'duration_weeks': course.duration_weeks,
            }
        )
        
        # Create BillingProduct record
        billing_product = BillingProduct.objects.create(
            course=course,
            stripe_product_id=product['id'],
            is_active=True
        )
        
        # Calculate prices using our price calculator
        prices = calculate_course_prices(course.price, course.duration_weeks)
        
        # Always create one-time price
        one_time_price = stripe_client.Price.create(
            product=product['id'],
            unit_amount=int(prices['one_time_price'] * 100),  # Convert to cents
            currency='usd',
            metadata={
                'course_id': str(course.id),
                'billing_type': 'one_time'
            }
        )
        
        # Create BillingPrice for one-time payment
        one_time_billing_price = BillingPrice.objects.create(
            product=billing_product,
            stripe_price_id=one_time_price['id'],
            billing_period='one_time',
            unit_amount=prices['one_time_price'],
            currency='usd',
            is_active=True
        )
        
        monthly_price = None
        # Create monthly subscription price if course is longer than 4 weeks
        if prices['total_months'] > 1:
            monthly_price = stripe_client.Price.create(
                product=product['id'],
                unit_amount=int(prices['monthly_price'] * 100),  # Convert to cents
                currency='usd',
                recurring={'interval': 'month'},
                metadata={
                    'course_id': str(course.id),
                    'billing_type': 'monthly',
                    'total_months': prices['total_months'],
                    'monthly_total': prices['monthly_total']
                }
            )
            
            # Create BillingPrice for monthly subscription
            monthly_billing_price = BillingPrice.objects.create(
                product=billing_product,
                stripe_price_id=monthly_price['id'],
                billing_period='monthly',
                unit_amount=prices['monthly_price'],
                currency='usd',
                is_active=True
            )
        
        return {
            'success': True,
            'product_id': product['id'],
            'one_time_price_id': one_time_price['id'],
            'monthly_price_id': monthly_price['id'] if monthly_price else None,
            'billing_strategy': 'monthly_and_one_time' if monthly_price else 'one_time_only',
            'price_details': prices
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def update_stripe_product_for_course(course):
    """
    Update Stripe product and prices when course is modified
    """
    try:
        stripe_client = get_stripe_client()
        
        # Get existing billing product
        billing_product = BillingProduct.objects.get(course=course)
        
        # Update Stripe product
        stripe_client.Product.modify(
            billing_product.stripe_product_id,
            name=course.title,
            description=course.description,
            metadata={
                'course_id': str(course.id),
                'teacher_id': str(course.teacher.id),
                'duration_weeks': course.duration_weeks,
            }
        )
        
        # Calculate new prices
        prices = calculate_course_prices(course.price, course.duration_weeks)
        
        # Deactivate all existing prices in Stripe and our database
        existing_prices = BillingPrice.objects.filter(product=billing_product, is_active=True)
        for price in existing_prices:
            # Archive the price in Stripe
            stripe_client.Price.modify(
                price.stripe_price_id,
                active=False
            )
            # Mark as inactive in our database
            price.is_active = False
            price.save()
        
        # Create new one-time price
        one_time_price = stripe_client.Price.create(
            product=billing_product.stripe_product_id,
            unit_amount=int(prices['one_time_price'] * 100),
            currency='usd',
            metadata={
                'course_id': str(course.id),
                'billing_type': 'one_time'
            }
        )
        
        # Create new BillingPrice for one-time payment
        BillingPrice.objects.create(
            product=billing_product,
            stripe_price_id=one_time_price['id'],
            billing_period='one_time',
            unit_amount=prices['one_time_price'],
            currency='usd',
            is_active=True
        )
        
        monthly_price = None
        # Create new monthly price if applicable
        if prices['total_months'] > 1:
            monthly_price = stripe_client.Price.create(
                product=billing_product.stripe_product_id,
                unit_amount=int(prices['monthly_price'] * 100),
                currency='usd',
                recurring={'interval': 'month'},
                metadata={
                    'course_id': str(course.id),
                    'billing_type': 'monthly',
                    'total_months': prices['total_months'],
                    'monthly_total': prices['monthly_total']
                }
            )
            
            # Create new BillingPrice for monthly subscription
            BillingPrice.objects.create(
                product=billing_product,
                stripe_price_id=monthly_price['id'],
                billing_period='monthly',
                unit_amount=prices['monthly_price'],
                currency='usd',
                is_active=True
            )
        
        return {
            'success': True,
            'product_id': billing_product.stripe_product_id,
            'one_time_price_id': one_time_price['id'],
            'monthly_price_id': monthly_price['id'] if monthly_price else None,
            'billing_strategy': 'monthly_and_one_time' if monthly_price else 'one_time_only',
            'price_details': prices
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def deactivate_stripe_product_for_course(course):
    """
    Deactivate Stripe product when course is archived
    """
    try:
        stripe_client = get_stripe_client()
        
        # Get existing billing product
        billing_product = BillingProduct.objects.get(course=course)
        
        # Archive Stripe product
        stripe_client.Product.modify(
            billing_product.stripe_product_id,
            active=False
        )
        
        # Deactivate billing product and prices
        billing_product.is_active = False
        billing_product.save()
        
        # Deactivate all prices
        BillingPrice.objects.filter(product=billing_product).update(is_active=False)
        
        return {'success': True}
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }