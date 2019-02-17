"""Views fro notes."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, Prefetch
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, UpdateView

from .forms import NoteForm
from .models import Series, Note, Locator
from .tag_filter import TagFilter
from .templatetags.note_lists import note_list_url


class NotesQuerysetMixin:
    """Get notes as the main query set with correct visibility and ordering."""

    def get_queryset(self, **kwargs):
        """Acquire the relevant series and return the notes in that series."""
        notes = (
            Note.objects
            .order_by(
                F('published').desc(),
                F('created').desc())
            .prefetch_related(
                Prefetch('subjects', queryset=Locator.objects.order_by('notesubject__sequence'))))
        if self.kwargs.get('drafts') and self.request.user.is_authenticated:
            series = Series.objects.filter(editors__login=self.request.user)
            notes = notes.filter(published__isnull=True, series__in=series)
        else:
            notes = notes.filter(published__isnull=False)
        return notes

    def get_context_data(self, **kwargs):
        """Add the series to the context."""
        context = super().get_context_data(**kwargs)
        context['drafts'] = self.kwargs.get('drafts', False)
        return context


class SeriesMixin(NotesQuerysetMixin):
    """Mixin for view classes for when the URL includes the series name."""

    series_required = True

    @cached_property
    def series(self):
        """The series of notes this page relates to."""
        series_name = getattr(self.request, 'series_name', None)
        return None if not series_name or series_name == '*' else get_object_or_404(Series, name=series_name)

    def get_queryset(self, **kwargs):
        notes = super().get_queryset()
        if self.series:
            return notes.filter(series=self.series)
        return notes

    def get_context_data(self, **kwargs):
        """Add the series to the context."""
        context = super().get_context_data(**kwargs)
        context['series'] = self.series
        context['can_edit_as'] = (
            self.request.user.is_authenticated
            and self.series
            and self.series.editors.filter(login=self.request.user))
        return context

    def dispatch(self, request, *args, **kwargs):
        if self.series_required and not self.series:
            return HttpResponseRedirect(reverse('about:index'))
        return super().dispatch(request, *args, **kwargs)


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


class IndexView(ListView):

    queryset = Series.objects.all()

    paginate_by = 60
    paginate_orphans = 3
    template_name = 'notes/index.html'


class LinksMixin:
    """Mixin to add Link header to response."""

    def get_links(self):
        """Override to add (rel, href) pairs."""
        return []

    def dispatch(self, request, *args, **kwargs):
        """Called to dispatch a request. Adds pagination links if needed."""
        response = super().dispatch(request, args, kwargs)
        response['Link'] = ', '.join('<%s>; rel=%s' % (href, rel) for rel, href in self.get_links())
        return response


class NoteListView(TaggedMixin, SeriesMixin, LinksMixin, ListView):

    paginate_by = 5
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
                self.links.append(('next', note_list_url(context, page=page_obj.next_page_number())))
            if page_obj.has_previous():
                self.links.append(('prev', note_list_url(context, page=page_obj.previous_page_number())))

        return context


class NoteDetailView(SeriesMixin, DetailView):

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


class NoteCreateView(LoginRequiredMixin, SeriesMixin, NoteFormMixin, CreateView):
    def form_valid(self, form):
        return super().form_valid(form)


class NoteUpdateView(LoginRequiredMixin, SeriesMixin, NoteFormMixin, UpdateView):

    def form_valid(self, form):
        if not form.instance.published and self.request.POST.get('publish_now'):
            form.instance.published = timezone.now()
        return super().form_valid(form)
