from django import template
register = template.Library()
@register.filter
def lower_alpha(value):
    """Convert a number to a lowercase letter (1 -> a, 2 -> b, etc.)."""
    return chr(96 + int(value))