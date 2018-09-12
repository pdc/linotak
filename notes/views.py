
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, F
from django.http import HttpResponse,  HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404, render
from django.views import generic
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.urls import reverse_lazy
from django.utils import timezone

from .forms import NoteForm
from .models import Series, Note


class NotesQuerysetMixin:
    """Get notes as the main query set with correct visibility and ordering."""
    def get_queryset(self, **kwargs):
        """Acquire the relevant series and return the notes in that series."""
        notes = Note.objects
        q = Q(published__isnull=False)
        if not self.request.user.is_anonymous:
            q = q | Q(series__in=self.request.user.series_set.all())
        return notes.filter(q).order_by(F('published').desc(nulls_first=True))

    def get_context_data(self, **kwargs):
        """Add flag saying whether there is a draft note already."""
        context = super().get_context_data(**kwargs)
        context['has_draft'] = self.get_queryset().filter(published__isnull=True).exists()
        return context


class SeriesMixin(NotesQuerysetMixin):
    """Mixin for view classes for when the URL includes the series name."""
    def get_queryset(self, **kwargs):
        self.series = get_object_or_404(Series, name=self.kwargs['series_name'])
        return super().get_queryset().filter(series=self.series)

    def get_context_data(self, **kwargs):
        """Add the seriies to the context."""
        context = super().get_context_data(**kwargs)
        context['series'] = self.series
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


class NoteCreateView(LoginRequiredMixin, NoteFormMixin, CreateView):
    def form_valid(self, form):
        self.series = get_object_or_404(Series, name=self.kwargs['series_name'])
        form.instance.series = self.series
        form.instance.author = self.request.user
        return super().form_valid(form)


class NoteUpdateView(LoginRequiredMixin, NoteFormMixin, UpdateView):
    def dispatch(self, *args, **kwargs):
        if self.get_object().published:
            messages.info(self.request, 'This note has already been published and cannot be edited.')
            return HttpResponsePermanentRedirect(self.get_object().get_absolute_url())
        return super().dispatch(*args, **kwargs)

    def form_valid(self, form):
        if not form.instance.published and self.request.POST.get('publish_now'):
            form.instance.published = timezone.now()
        return super().form_valid(form)
