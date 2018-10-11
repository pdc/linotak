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


class TestNoteExtractSubjects(TestCase):
    """Test Note.extract_subjects."""

    def test_converts_http_link(self):
        note = NoteFactory.create(text='http://example.com/1')

        result = note.extract_subject()

        self.assertTrue(result)
        self.assertFalse(note.text)  # No text remains
        self.assertEqual([x.url for x in note.subjects.all()], ['http://example.com/1'])

    def test_retains_balance_of_text(self):
        note = NoteFactory.create(text='Why hello! http://example.com/1')

        result = note.extract_subject()

        self.assertTrue(result)
        self.assertEqual(note.text, 'Why hello!')
        self.assertEqual([x.url for x in note.subjects.all()], ['http://example.com/1'])

    def test_strips_whitespace(self):
        note = NoteFactory.create(text='Why hello!\n\n http://example.com/1 \n\n')

        result = note.extract_subject()

        self.assertTrue(result)
        self.assertEqual(note.text, 'Why hello!')
        self.assertEqual([x.url for x in note.subjects.all()], ['http://example.com/1'])

    def test_ignores_urls_with_text_following(self):
        note = NoteFactory.create(text='http://example.com/1 Blort')

        result = note.extract_subject()

        self.assertFalse(result)
        self.assertEqual(note.text, 'http://example.com/1 Blort')
        self.assertEqual([x.url for x in note.subjects.all()], [])

    def test_matches_multiple_urls(self):
        note = NoteFactory.create(text='Many! http://example.com/1 https://example.com/2')

        result = note.extract_subject()

        self.assertTrue(result)
        self.assertEqual(note.text, 'Many!')
        self.assertEqual([x.url for x in note.subjects.all()], ['http://example.com/1', 'https://example.com/2'])

    def test_matches_with_empty_path(self):
        note = NoteFactory.create(text='Yo! http://example.com/')

        result = note.extract_subject()

        self.assertTrue(result)
        self.assertEqual(note.text, 'Yo!')
        self.assertEqual([x.url for x in note.subjects.all()], ['http://example.com/'])


    def test_matches_URL_sans_path(self):
        note = NoteFactory.create(text='Yo! http://example.com')

        result = note.extract_subject()

        self.assertTrue(result)
        self.assertEqual(note.text, 'Yo!')
        self.assertEqual([x.url for x in note.subjects.all()], ['http://example.com/'])


    def test_returns_false_if_no_urls(self):
        note = NoteFactory.create(text='Banana frappé')

        result = note.extract_subject()

        self.assertFalse(result)
        self.assertEqual(note.text, 'Banana frappé')
        self.assertEqual([x.url for x in note.subjects.all()], [])
