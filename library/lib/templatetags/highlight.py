import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(is_safe=False)
def highlight(value, query):
    """Highlight occurrences of `query` inside `value` using a <mark> tag.

    - Case-insensitive
    - Escapes the original value to avoid XSS
    - Returns a SafeString containing <mark> wrapped matches
    - If query is falsy, returns the escaped value unchanged
    """
    if not value:
        return ''
    try:
        q = (query or '').strip()
    except Exception:
        q = ''

    # Escape original value first
    text = escape(value)
    if not q:
        return mark_safe(text)

    # Build a regex for the query, escaping any regex meta-characters
    try:
        pattern = re.compile(re.escape(q), re.IGNORECASE)
    except re.error:
        return mark_safe(text)

    # Replace matches with <mark>...</mark>
    highlighted = pattern.sub(lambda m: f"<mark class=\"highlight\">{m.group(0)}</mark>", text)
    return mark_safe(highlighted)
