from datetime import datetime

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import Note
from .factories import NoteFactory, SeriesFactory


class TestFactories(TestCase):
    """Test Factories."""

    def test_note_has_author_who_is_editor_in_series(self):
        note = NoteFactory.create()

        self.assertTrue(note.author.native_name)
        self.assertTrue(note.series.editors.filter(pk=note.author.pk).exists())

    def test_note_with_series(self):
        series = SeriesFactory.create()
        note = NoteFactory.create(series=series)

        self.assertTrue(note.author.native_name)
        self.assertTrue(note.series.editors.filter(pk=note.author.pk).exists())

