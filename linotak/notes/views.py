"""Views for notes."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, AccessMixin
from django.db.models import F, Prefetch
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ngettext
from django.views.generic import DetailView, ListView, FormView
from django.views.generic.edit import CreateView, UpdateView

from .forms import NoteForm, LocatorImageFormSet
from .models import Person, Series, Note, Locator, LocatorImage
from .tag_filter import TagFilter
from .templatetags.note_lists import note_list_url


class SeriesMixin():
    """Mixin for view classes for when the URL includes the series name."""

    @cached_property
    def series(self):
        """The series of notes this page relates to."""
        series_name = getattr(self.request, 'series_name', None)
        return None if not series_name else get_object_or_404(Series, name=series_name)

    def get_context_data(self, **kwargs):
        """Add the series to the context."""
        context = super().get_context_data(**kwargs)
        context['series'] = self.series
        context['can_edit_as'] = (
            self.request.user.is_authenticated
            and self.series
            and self.series.editors.filter(login=self.request.user))
        return context


class SeriesRequiredMixin(SeriesMixin):
    def dispatch(self, request, *args, **kwargs):
        if not self.series:
            return HttpResponseRedirect(reverse('about:index'))
        return super().dispatch(request, *args, **kwargs)


class NotesMixin(SeriesRequiredMixin):
    """Get notes as the main query set with correct visibility and ordering.

    (Includes SeriesRequiredMixin hence also acquires series from request.)
    """

    def get_queryset(self, **kwargs):
        """Acquire the relevant series and return the notes in that series."""
        notes = (
            Note.objects
            .order_by(
                F('published').desc(),
                F('created').desc())
            .prefetch_related(
                Prefetch('subjects', queryset=Locator.objects.order_by('notesubject__sequence'))))
        if self.series:
            notes = notes.filter(series=self.series)
        if self.kwargs.get('drafts') and self.request.user.is_authenticated:
            series_list = Series.objects.filter(editors__login=self.request.user)
            notes = notes.filter(published__isnull=True, series__in=series_list)
        else:
            notes = notes.filter(published__isnull=False)
        return notes

    def get_context_data(self, **kwargs):
        """Add the series to the context."""
        context = super().get_context_data(**kwargs)
        context['drafts'] = self.kwargs.get('drafts', False)
        return context


class TaggedMixin:

    @cached_property
    def tag_filter(self):
        """TagFilter instance implied by URL, or None."""
        return TagFilter.parse(self.kwargs.get('tags'))

    def get_queryset(self, **kwargs):
        """Filter by tags if specified."""
        queryset = super().get_queryset()
        tag_filter = self.tag_filter
        if tag_filter:
            queryset = tag_filter.apply(queryset)
        return queryset

    def get_context_data(self, **kwargs):
        """Add the series to the context."""
        context = super().get_context_data(**kwargs)
        context['tag_filter'] = self.tag_filter
        return context


class Link:
    """Link to another resource to be included on page."""

    def __init__(self, rel, href, media_type=None):
        self.rel = rel
        self.href = href
        self.media_type = media_type

    def to_link_header(self):
        if self.media_type:
            return '<%s>; rel=%s; type=%s' % (self.href, self.rel, self.media_type)
        return '<%s>; rel=%s' % (self.href, self.rel)

    def to_unique(self):
        if self.media_type:
            return self.rel, self.href, self.media_type
        return self.rel, self.href

    def __eq__(self, other):
        return isinstance(other, Link) and self.to_unique() == other.to_unique()

    def __repr__(self):
        return 'Link%r' % (self.to_unique(),)

    def __str__(self):
        return self.to_link_header()


class LinksMixin:
    """Mixin to add Link header to response."""

    def get_links(self):
        """Override to add Link instances."""
        return []

    def dispatch(self, request, *args, **kwargs):
        """Called to dispatch a request. Adds pagination links if needed."""
        response = super().dispatch(request, args, kwargs)
        response['Link'] = ', '.join(x.to_link_header() for x in self.get_links())
        return response

    def get_context_data(self, **kwargs):
        """Get context data, and also add links to context.

        Returns a factory function so as to defer until actually needed in template.
        This is because some get_links methods call get_context_data and
        we want to avoid mutual recursion!
        """
        context = super().get_context_data(**kwargs)
        context['links'] = lambda: self.get_links()
        return context


class LoginRequiredIfDraftMixin(AccessMixin):
    """Mixxin that checks user is logged in if the request is for draft notes."""

    def dispatch(self, request, *args, **kwargs):
        if self.kwargs.get('drafts') and (not request.user.is_authenticated or not self.series.editors.filter(login=request.user).exists()):
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)


class NoteListView(LoginRequiredIfDraftMixin, TaggedMixin, NotesMixin, LinksMixin, ListView):

    paginate_by = 9
    paginate_orphans = 3
    links = None

    def get_links(self):
        if self.links is None:
            self.get_context_data()  # self.links is created as a side effect.
        return super().get_links() + self.links

    def get_context_data(self, **kwargs):
        """Get context data, and also set pagination links."""
        context = super().get_context_data(**kwargs)

        self.links = []
        page_obj = context.get('page_obj')
        if 'page_obj':
            if page_obj.has_next():
                self.links.append(Link('next', note_list_url(context, page=page_obj.next_page_number())))
            if page_obj.has_previous():
                self.links.append(Link('prev', note_list_url(context, page=page_obj.previous_page_number())))
        if not self.kwargs.get('drafts'):
            self.links.append(Link('alternate', note_list_url(context, 'feed'), 'application/atom+xml'))

        return context


class NoteDetailView(LoginRequiredIfDraftMixin, NotesMixin, LinksMixin, DetailView):

    def get_links(self):
        """Add link to Webmention endpoint."""
        return super().get_links() + [Link('webmention', reverse('webmention'))]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['puff'] = 4
        return context


class NoteFormMixin:
    model = Note
    form_class = NoteForm

    def get_initial(self, **kwargs):
        """Ensure series is propagated down in to the form."""
        initial = super().get_initial(**kwargs)
        initial['series'] = self.series
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['login'] = self.request.user
        return kwargs


class NoteCreateView(LoginRequiredMixin, NotesMixin, NoteFormMixin, CreateView):
    def form_valid(self, form):
        return super().form_valid(form)


class NoteUpdateView(LoginRequiredMixin, NotesMixin, NoteFormMixin, UpdateView):

    def form_valid(self, form):
        if not form.instance.published and self.request.POST.get('publish_now'):
            form.instance.published = timezone.now()
        return super().form_valid(form)


class PersonDetailView(LinksMixin, SeriesMixin, DetailView):
    """Information about a person (only allowed if that person has a slug)."""

    model = Person

    def get_links(self):
        links = super().get_links()
        if self.series:
            links.append(Link(href=self.series.get_absolute_url(), rel='feed'))
        return links


class LocatorImagesView(SeriesMixin, FormView):

    form_class = LocatorImageFormSet
    template_name = 'notes/locator_image_list.html'

    @cached_property
    def locator(self):
        """Locator specified in the URL."""
        return self.note.subjects.get(pk=self.kwargs['locator_pk'])

    @cached_property
    def note(self):
        """Note specified in the URL."""
        return self.series.note_set.get(pk=self.kwargs['pk'])

    def get_form_kwargs(self):
        """Get formset with images from locator."""
        kwargs = super().get_form_kwargs()
        kwargs['queryset'] = self.get_queryset()
        return kwargs

    def get_queryset(self):
        """Images associated with locator."""
        return (
            LocatorImage.objects.filter(locator=self.locator)
            .order_by(
                '-prominence',
                (F('image__width') * F('image__height')).desc(nulls_last=True))
        )

    def get_context_data(self, **kwargs):
        """Add the series to the context."""
        context = super().get_context_data(**kwargs)
        context['formset'] = context['form']  # Pretend FormView is actually FormsetView
        context['note'] = self.note
        context['locator'] = self.locator
        return context

    def get_success_url(self):
        return self.note.get_absolute_url()

    def form_valid(self, formset, *args, **kwargs):
        xs = formset.save()  # List of LocatorImage instances that were changed
        if xs:
            messages.add_message(self.request, messages.INFO, ngettext(
                'Updated one image’s prominence',
                'Updated prominence on %(count)d images',
                len(xs),
            ) % {'count': len(xs)})

        return super().form_valid(formset, *args, *kwargs)
