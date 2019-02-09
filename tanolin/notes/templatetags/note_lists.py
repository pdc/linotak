"""Template tags for image representations."""

from django import template
from django.urls import reverse


register = template.Library()


@register.simple_tag(takes_context=True)
def note_list_url(context, series=None, tag_filter=None, drafts=None, page=None):
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
    if series is None:
        series = context.get('series')
    if tag_filter is None:
        tag_filter = context.get('tag_filter')
    if drafts is None:
        drafts = context.get('drafts')
    if page is None:
        page = context.get('page_obj')

    if page and hasattr(page, 'number'):
        page = page.number

    return reverse('notes:list', kwargs={
        'series_name': '*' if series == '*' else series.name if series else '*',
        'tags': tag_filter.unparse() if tag_filter else '',
        'drafts': drafts,
        'page': page or 1,
    })
