from django import template

register = template.Library()

@register.filter
def charformat(value, format_type):
    if format_type == 'ALPHA':
        return chr(64 + int(value))
    return value