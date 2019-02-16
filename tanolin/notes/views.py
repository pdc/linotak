"""Views fro notes."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import generic
from django.views.generic.edit import CreateView, UpdateView

from .forms import NoteForm
from .models import Series, Note
from .tag_filter import TagFilter


class NotesQuerysetMixin:
    """Get notes as the main query set with correct visibility and ordering."""

    def get_queryset(self, **kwargs):
        """Acquire the relevant series and return the notes in that series."""
        notes = Note.objects.order_by(
            F('published').desc(),
            F('created').desc())
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

    @cached_property
    def series(self):
        """The series of notes this page relates to."""
        series_name = getattr(self.request, 'series_name', None)
        return None if series_name == '*' else get_object_or_404(Series, name=series_name)

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


class IndexView(generic.ListView):

    queryset = Series.objects.all()

    paginate_by = 60
    paginate_orphans = 3
    template_name = 'notes/index.html'


class NoteListView(TaggedMixin, SeriesMixin, generic.ListView):

    paginate_by = 30
    paginate_orphans = 3


class NoteDetailView(SeriesMixin, generic.DetailView):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['puff'] = 3
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
