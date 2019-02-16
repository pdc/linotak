"""Template tags for image representations."""

from django import template
from django.conf import settings
from django.urls import reverse


register = template.Library()


@register.simple_tag(takes_context=True)
def note_list_url(context, view=None, series=None, tag_filter=None, drafts=None, page=None):
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
    if view and view != 'list':
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
        path = reverse('notes:list', kwargs={
            'tags': tag_filter.unparse() if tag_filter else '',
            'drafts': drafts or False,
            'page': page or 1,
        })
    if series != context_series:
        return '//%s.%s%s' % (series.name if hasattr(series, 'name') else series, settings.NOTES_DOMAIN, path)
    return path


@register.simple_tag(takes_context=True)
def note_url(context, view=None, note=None, tag_filter=None, drafts=None):
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

    path = reverse('notes:%s' % (view or 'detail'), kwargs={
        'pk': note.pk,
        'tags': tag_filter.unparse() if tag_filter else '',
        'drafts': drafts or False,
    })
    if note.series != context_series:
        return '//%s.%s%s' % (note.series.name, settings.NOTES_DOMAIN, path)
    return path
