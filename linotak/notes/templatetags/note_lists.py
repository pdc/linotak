"""Template tags for image representations."""

from django import template
from django.urls import reverse

from ..models import make_absolute_url


register = template.Library()


@register.simple_tag(takes_context=True)
def note_list_url(context, view=None, series=None, tag_filter=None, drafts=None, page=None, with_host=False):
    """Like url tag except specialized for links to note lists.

    Arguments --
        series -- Series instance
        tag_filter -- TagFilter instance
        drafts -- boolean
        page -- integer

    All arguments are optional and will be acquired from the context
    if omitted.
    """
    # Acquire from context if not specified in arguments.
    context_series = context.get('series')
    if series is None:
        series = context_series
    kwargs = {}
    if view and view not in ('list', 'feed'):
        path = reverse('notes:%s' % view, kwargs=kwargs)
    else:
        if tag_filter is None:
            tag_filter = context.get('tag_filter')
        if drafts is None:
            drafts = context.get('drafts')
        if page is None:
            page = context.get('page_obj')
        if page and hasattr(page, 'number'):
            page = page.number
        path = reverse('notes:%s' % (view or 'list'), kwargs={
            'tags': tag_filter.unparse() if tag_filter else '',
            'drafts': drafts or False,
            'page': (page or 1) if not view or view == 'list' else 1,
        })
    if with_host or series != context_series:
        return series.make_absolute_url(path)
    return path


@register.simple_tag(takes_context=True)
def note_url(context, view=None, note=None, tag_filter=None, drafts=None, with_host=False, **kwargs):
    """Like url tag except specialized for links to note lists.

    Arguments --
        view -- names a notes view, e.g., 'edit'
        note -- Note instance
        tag_filter -- TagFilter instance
        drafts -- boolean

    All arguments are optional and will be acquired from the context
    if omitted. Except view is optional and defaults to detail
    """
    # Acquire from context if not specified in arguments.
    context_series = context.get('series')
    if note is None:
        note = context.get('note')
    if tag_filter is None:
        tag_filter = context.get('tag_filter')
    if drafts is None:
        drafts = context.get('drafts')
    return note.get_absolute_url(
        view=view,
        tag_filter=tag_filter,
        drafts=(drafts if drafts is not None else note and not note.published),
        with_host=(with_host or note.series != context_series),
        **kwargs,
    )


@register.simple_tag(takes_context=True)
def profile_url(context, person=None, series=None):
    """Link to the profile of this person (or the subject of this page if no person specified)."""
    path = reverse('notes:person', kwargs={'slug': (person or context['person']).slug})
    if not series:
        series = context.get('series')
    return series.make_absolute_url(path) if series else make_absolute_url(path)

