"""Template tags for image representations."""

from django import template

from ..tag_filter import TagFilter


register = template.Library()


@register.filter
def with_included(value, arg):
    """Given a tag filter, return one with an additional arg."""
    tag_name = arg.name if hasattr(arg, 'name') else arg
    if not value:
        return TagFilter([tag_name])
    tag_filter = value
    return TagFilter(tag_filter.included | set([tag_name]), tag_filter.excluded)
