"""
Utility functions for calculating course prices
"""
from decimal import Decimal
import math
from settings.models import CourseSettings


def calculate_course_prices(one_time_price: float, duration_weeks: int) -> dict:
    """
    Calculate course prices based on duration and one-time price.
    
    Logic:
    1. One-time price: Use as is
    2. Monthly price: 
       - Add 15% to one-time price
       - Divide by number of months (duration_weeks / 4)
       
    Args:
        one_time_price (float): Teacher's set price
        duration_weeks (int): Course duration in weeks
        
    Returns:
        dict: {
            'one_time_price': float,
            'monthly_price': float,
            'total_months': int,
            'monthly_total': float  # monthly_price * total_months
        }
    
    Example:
        >>> calculate_course_prices(300, 8)
        {
            'one_time_price': 300.00,
            'monthly_price': 172.50,
            'total_months': 2,
            'monthly_total': 345.00
        }
    """
    # Convert to Decimal for precise calculations
    one_time = Decimal(str(one_time_price))
    
    # Calculate number of months (round up to nearest month)
    total_months = math.ceil(duration_weeks / 4)
    
    # Get markup percentage from settings
    settings = CourseSettings.get_settings()
    markup_decimal = (Decimal(str(settings.monthly_price_markup_percentage)) / Decimal('100')) + Decimal('1')
    
    # Apply markup to one-time price for monthly calculation
    monthly_total = one_time * markup_decimal
    
    # Calculate per-month price
    monthly_price = monthly_total / total_months
    
    # Round all prices to 2 decimal places
    return {
        'one_time_price': float(one_time.quantize(Decimal('0.01'))),
        'monthly_price': float(monthly_price.quantize(Decimal('0.01'))),
        'total_months': total_months,
        'monthly_total': float(monthly_total.quantize(Decimal('0.01')))
    }
