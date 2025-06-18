from django import template
register = template.Library()
@register.filter(name='get_item')
def get_item(dictionary, key):
    return dictionary.get(key)


from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, False)