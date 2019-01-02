"""Test updating."""

from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
import httpretty
from unittest.mock import patch

from ...images.models import Image
from ..models import Locator
from ..updating import fetch_page_update_locator, update_locator_with_stuff
from ..scanner import Title, HCard, HEntry, Img
from .. import updating


class TestFetchPageUpdateLocator(TestCase):
    """Test fetch_page_update_locator."""

    @httpretty.activate(allow_net_connect=False)
    def test_requests_data_and_scans_when_new(self):
        self.assert_requests_data_when(locator_scanned=None, if_not_scanned_since=None)

    @httpretty.activate(allow_net_connect=False)
    def test_requests_data_and_scans_when_scanned_in_past(self):
        then = timezone.now() - timedelta(days=8)
        self.assert_requests_data_when(locator_scanned=then, if_not_scanned_since=then)

    @httpretty.activate(allow_net_connect=False)
    def test_doesnt_request_data_when_scanned_more_recently(self):
        then = timezone.now() - timedelta(days=8)
        more_recently = timezone.now() - timedelta(days=1)
        self.assert_doesnt_request_data_when(locator_scanned=more_recently, if_not_scanned_since=then)

    @httpretty.activate(allow_net_connect=False)
    def test_doesnt_request_data_when_scanned_since_new(self):
        then = timezone.now() - timedelta(days=8)
        self.assert_doesnt_request_data_when(locator_scanned=then, if_not_scanned_since=None)

    def assert_requests_data_when(self, locator_scanned, if_not_scanned_since):
        locator = Locator.objects.create(url='https://example.com/1', scanned=locator_scanned)
        with patch.object(updating, 'PageScanner') as cls, patch.object(updating, 'update_locator_with_stuff') as mock_update:
            page_scanner = cls.return_value
            httpretty.register_uri(
                httpretty.GET, 'https://example.com/1',
                body='CONTENT OF PAGE',
            )
            page_scanner.stuff = ['**STUFF**']

            result = fetch_page_update_locator(locator, if_not_scanned_since=if_not_scanned_since)

            self.assertTrue(result)
            cls.assert_called_with('https://example.com/1')
            page_scanner.feed.assert_called_with('CONTENT OF PAGE')
            page_scanner.close.assert_called_with()

            mock_update.assert_called_once_with(locator, ['**STUFF**'])
            updated = Locator.objects.get(pk=locator.pk)
            self.assertTrue(updated.scanned)

    def assert_doesnt_request_data_when(self, locator_scanned, if_not_scanned_since):
        locator = Locator.objects.create(url='https://example.com/1', scanned=locator_scanned)
        with patch.object(updating, 'PageScanner') as cls:
            # Httpretty should complain if any call is made because none is registered.

            result = fetch_page_update_locator(locator, if_not_scanned_since=if_not_scanned_since)

            self.assertFalse(result)
            self.assertFalse(cls.called)


class TestUpdateLocatorWithStuff(TestCase):
    """Test update_locator_with_stuff."""

    @classmethod
    def setUpTestData(cls):
        cls.locator = Locator.objects.create(url='https://example.com/1')

    def test_uses_title(self):
        update_locator_with_stuff(self.locator, [Title('TITLE OF PAGE')])

        self.assertEqual(self.locator.title, 'TITLE OF PAGE')

    def test_uses_hentry(self):
        update_locator_with_stuff(self.locator, [
            HEntry(
                'https://example.com/1', 'NAME', 'SUMMARY',
                HCard('AUTHOR', 'https://example.com/author'),
            ),
        ])

        self.assertEqual(self.locator.title, 'NAME')
        self.assertEqual(self.locator.text, 'SUMMARY')

    def test_uses_hentry_over_title(self):
        update_locator_with_stuff(self.locator, [
            HEntry(
                'https://example.com/1', 'NAME', 'SUMMARY',
                HCard('AUTHOR', 'https://example.com/author'),
            ),
            Title('OTHER TITLE'),
        ])

        self.assertEqual(self.locator.title, 'NAME')

    def test_uses_toplevel_images(self):
        update_locator_with_stuff(self.locator, [
            Img('https://images.example.com/42'),
        ])

        self.assertEqual(self.locator.images.all()[0].data_url, 'https://images.example.com/42')

    def test_copies_media_type_and_size(self):
        update_locator_with_stuff(self.locator, [
            Img('https://images.example.com/42', type='image/jpeg', width=1001, height=997),
        ])

        self.assertEqual(self.locator.images.all().count(), 1)
        actual = self.locator.images.all()[0]
        self.assertEqual(actual.data_url, 'https://images.example.com/42')
        self.assertEqual(actual.media_type, 'image/jpeg')
        self.assertEqual(actual.width, 1001)
        self.assertEqual(actual.height, 997)

    def test_doesnt_clobber_existing_metadata(self):
        self.locator.images.add(Image.objects.create(data_url='https://images.example.com/69', media_type='application/octet-stream', width=1280, height=960))
        update_locator_with_stuff(self.locator, [
            Img('https://images.example.com/69', type='image/jpeg'),
        ])

        actual = self.locator.images.all()[0]
        self.assertEqual(actual.media_type, 'image/jpeg')
        self.assertEqual(actual.width, 1280)
        self.assertEqual(actual.height, 960)

    def xtest_uses_hcard(self):
        update_locator_with_stuff(self.locator, [
            HEntry(
                'https://example.com/1', 'NAME', 'SUMMARY',
                HCard('AUTHOR', 'https://example.com/author')),
            ])

        self.assertEqual(self.locator.author.native_name, 'AUTHOR')
        self.assertEqual(self.locator.author.profile.url, 'https://example.com/author')
