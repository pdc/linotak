from django.shortcuts import get_object_or_404, render

from linotak.notes.models import Series

from .pages import Page


def page_view(request, name=None):
    """Display the page with this name, or the index page."""
    page = Page.find_with_name(name)
    series = (
        get_object_or_404(Series, name=request.series_name)
        if hasattr(request, "series_name")
        else None
    )
    page.set_context({"series": series}, request)
    return render(
        request,
        "about/page.html",
        {
            "page": page,
            "series": series,
        },
    )
