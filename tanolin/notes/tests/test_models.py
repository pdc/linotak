from django.db import transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from unittest.mock import patch

from ...matchers_for_mocks import DateTimeTimestampMatcher
from ...images.models import Image, wants_data
from ..models import Locator
from .. import tasks
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


class TestLocatorFetchPageUpdate(TransactionTestCase):
    """Test locator_fetch_page_update."""

    def test_queues_fetch_when_locator_created(self):
        """Test locator_fetch_page_update queues fetch when locator created."""
        with self.settings(NOTES_FETCH_LOCATORS=True), patch.object(tasks, 'fetch_locator_page') as fetch_locator_page:
            with transaction.atomic():
                locator = Locator.objects.create(url='https://example.com/1')

                self.assertFalse(fetch_locator_page.delay.called)
                # Not queued during the transaction to avoid race condition.

            fetch_locator_page.delay.assert_called_once_with(locator.pk, if_not_scanned_since=None)

    def test_doesnt_queue_if_settings_not_set(self):
        """Test locator_fetch_page_update doesnt queue if settings not set."""
        with self.settings(NOTES_FETCH_LOCATORS=False), patch.object(tasks, 'fetch_locator_page') as fetch_locator_page:
            Locator.objects.create(url='https://example.com/1')

            self.assertFalse(fetch_locator_page.delay.called)

    def test_doesnt_queue_if_not_newly_created(self):
        """Test locator_fetch_page_update doesnt queue if not newly created"""
        with self.settings(NOTES_FETCH_LOCATORS=True), patch.object(tasks, 'fetch_locator_page') as fetch_locator_page:
            locator = Locator.objects.create(url='https://example.com/1')
            locator.title = 'FOO'
            locator.save()

            fetch_locator_page.delay.assert_called_once_with(locator.pk, if_not_scanned_since=None)


class LocatorQueueFetch(TransactionTestCase):

    def test_passes_none_if_never_scanned(self):
        locator = Locator.objects.create(url='https://example.com/1')

        with patch.object(tasks, 'fetch_locator_page') as fetch_locator_page:
            locator.queue_fetch()

        fetch_locator_page.delay.assert_called_once_with(locator.pk, if_not_scanned_since=None)

    def test_value_that_can_return_original_datetime(self):
        locator = Locator.objects.create(url='https://example.com/1', scanned=timezone.now())

        with patch.object(tasks, 'fetch_locator_page') as fetch_locator_page:
            locator.queue_fetch()

        fetch_locator_page.delay.assert_called_once_with(locator.pk, if_not_scanned_since=DateTimeTimestampMatcher(locator.scanned))


class TestLocatorMainImage(TestCase):

    def test_returns_largest_image(self):
        locator = Locator.objects.create(url='https://example.com/1')
        locator.images.add(Image.objects.create(data_url='https://example.com/100', width=100, height=50))
        locator.images.add(Image.objects.create(data_url='https://example.com/500', width=500, height=400))
        locator.images.add(Image.objects.create(data_url='https://example.com/50', width=60, height=60))

        result = locator.main_image()

        self.assertEqual(result.data_url, 'https://example.com/500')

    def test_queues_retrieval_of_unsized_images(self):
        locator = Locator.objects.create(url='https://example.com/1')
        locator.images.add(Image.objects.create(data_url='https://example.com/100', width=100, height=50))
        image = Image.objects.create(data_url='https://example.com/500')
        locator.images.add(image)
        locator.images.add(Image.objects.create(data_url='https://example.com/50', width=60, height=60))

        with patch.object(wants_data, 'send') as wants_data_send:
            result = locator.main_image()

        self.assertEqual(result.data_url, 'https://example.com/100')
        wants_data_send.assert_called_once_with(Image, instance=image)