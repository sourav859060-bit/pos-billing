from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def inr(value):
    try:
        return f"₹{Decimal(str(value)):.2f}"
    except (InvalidOperation, TypeError, ValueError):
        return "₹0.00"
