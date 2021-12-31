"""Template tags for image representations."""

from django import template
from functools import wraps

from ..tag_filter import TagFilter


register = template.Library()


def expects_tag_name(func):
    """Decorator for these filter defintions that apply to a tag."""

    @wraps(func)
    def wrapped_func(value, arg):
        tag_name = arg.name if hasattr(arg, "name") else arg
        return func(value, tag_name)

    return wrapped_func


@register.filter
@expects_tag_name
def with_included(tag_filter, tag_name):
    """Given a tag filter, return one with an additional arg."""
    if tag_filter:
        return TagFilter(tag_filter.included | set([tag_name]), tag_filter.excluded)
    return TagFilter([tag_name])


@register.filter
@expects_tag_name
def without_included(tag_filter, tag_name):
    """Given a tag filter, return one with an additional arg."""
    if tag_filter:
        return (
            TagFilter(tag_filter.included - set([tag_name]), tag_filter.excluded) or ""
        )


@register.filter
@expects_tag_name
def with_excluded(tag_filter, tag_name):
    """Given a tag filter, return one with an additional arg."""
    if tag_filter:
        return TagFilter(tag_filter.included, tag_filter.excluded | set([tag_name]))
    return TagFilter(None, [tag_name])


@register.filter
@expects_tag_name
def without_excluded(tag_filter, tag_name):
    """Given a tag filter, return one with an additional arg."""
    if tag_filter:
        return (
            TagFilter(tag_filter.included, tag_filter.excluded - set([tag_name])) or ""
        )


@register.filter
def unparse(tag_filter):
    return tag_filter.unparse() if tag_filter else ""
