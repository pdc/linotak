
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, F
from django.http import HttpResponse,  HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import generic
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from .forms import NoteForm, LocatorFormset
from .models import Series, Note, Locator


class NotesQuerysetMixin:
    """Get notes as the main query set with correct visibility and ordering."""

    def get_queryset(self, **kwargs):
        """Acquire the relevant series and return the notes in that series."""
        return Note.objects.order_by(
            F('published').desc(),
            F('created').desc())

    def get_context_data(self, **kwargs):
        """If user is editor and there is a note list then partition the list in to published & unpublished."""
        context = super().get_context_data(**kwargs)
        notes = context.get('note_list')
        if notes:
            context['note_list'] = notes.filter(published__isnull=False)
            if self.request.user.is_authenticated:
                series = Series.objects.filter(editors__login=self.request.user)
                context['draft_list'] = notes.filter(published__isnull=True, series__in=series)
        return context


class SeriesMixin(NotesQuerysetMixin):
    """Mixin for view classes for when the URL includes the series name."""

    @cached_property
    def series(self):
        """The series of notes this page relates to."""
        return get_object_or_404(Series, name=self.kwargs['series_name'])

    def get_queryset(self, **kwargs):
        return super().get_queryset().filter(series=self.series)

    def get_context_data(self, **kwargs):
        """Add the seriies to the context."""
        context = super().get_context_data(**kwargs)
        context['series'] = self.series
        context['can_edit_as'] = (
            self.request.user.is_authenticated
            and self.series.editors.filter(login=self.request.user))
        return context


class IndexView(NotesQuerysetMixin, generic.ListView):
    template_name = 'notes/index.html'


class NoteListView(SeriesMixin, generic.ListView):
    pass


class NoteDetailView(SeriesMixin, generic.DetailView):
    pass


class NoteFormMixin:
    model = Note
    form_class = NoteForm

    def get_initial(self, **kwargs):
        initial = super().get_initial(**kwargs)
        initial['author'] = self.request.user.person_set.all()[0]
        initial['series'] = self.series
        return initial


class NoteCreateView(LoginRequiredMixin, SeriesMixin, NoteFormMixin, CreateView):
    def form_valid(self, form):
        return super().form_valid(form)


class NoteUpdateView(LoginRequiredMixin, SeriesMixin, NoteFormMixin, UpdateView):
    def dispatch(self, *args, **kwargs):
        if self.get_object().published:
            messages.info(self.request, 'This note has already been published and cannot be edited.')
            return HttpResponsePermanentRedirect(self.get_object().get_absolute_url())
        return super().dispatch(*args, **kwargs)

    def form_valid(self, form):
        if not form.instance.published and self.request.POST.get('publish_now'):
            form.instance.published = timezone.now()
        return super().form_valid(form)
