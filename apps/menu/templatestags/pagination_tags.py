# apps/menu/templatetags/pagination_tags.py
from django import template
from urllib.parse import urlencode

register = template.Library()

@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """
    Returns the URL query string with updated parameters while preserving existing ones.
    Usage: {% query_transform page=page_number %}
    """
    query = context['request'].GET.copy()
    for k, v in kwargs.items():
        query[k] = v
    return query.urlencode()