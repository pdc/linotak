"""Test updating."""

from django.test import TestCase
import httpretty
from unittest.mock import patch, MagicMock

from ..models import Locator
from ..updating import fetch_page_update_locator, update_locator_with_stuff
from ..scanner import Title, HCard, HEntry
from .. import updating


@httpretty.activate
class TestFetchPageUpdateLocator(TestCase):
    """Test fetch_page_update_locator."""

    def test_requests_data(self):
        locator = Locator.objects.create(url='https://example.com/1')
        with patch.object(updating, 'PageScanner') as cls, patch.object(updating, 'update_locator_with_stuff') as mock_update:
            page_scanner = cls.return_value
            httpretty.register_uri(
                httpretty.GET, 'https://example.com/1',
                body='CONTENT OF PAGE',
            )
            cls.return_value.stuff = ['**STUFF**']

            fetch_page_update_locator(locator)

            cls.assert_called_with('https://example.com/1')
            page_scanner.feed.assert_called_with('CONTENT OF PAGE')
            page_scanner.close.assert_called_with()

            mock_update.assert_called_once_with(locator, ['**STUFF**'])


class TestUpdateLocatorWithStuff(TestCase):
    """Test update_locator_with_stuff."""

    def test_uses_title(self):
        locator = Locator.objects.create(url='https://example.com/1')

        update_locator_with_stuff(locator, [Title('TITLE OF PAGE')])

        updated = Locator.objects.get(pk=locator.pk)
        self.assertEqual(updated.title, 'TITLE OF PAGE')

    def test_uses_hentry(self):
        locator = Locator.objects.create(url='https://example.com/1')

        update_locator_with_stuff(locator, [
            HEntry(
                'https://example.com/1', 'NAME', 'SUMMARY',
                HCard('AUTHOR', 'https://example.com/author'),
            ),
        ])

        updated = Locator.objects.get(pk=locator.pk)
        self.assertEqual(updated.title, 'NAME')
        self.assertEqual(updated.text, 'SUMMARY')

    def test_uses_hentry_over_title(self):
        locator = Locator.objects.create(url='https://example.com/1')

        update_locator_with_stuff(locator, [
            HEntry(
                'https://example.com/1', 'NAME', 'SUMMARY',
                HCard('AUTHOR', 'https://example.com/author'),
            ),
            Title('OTHER TITLE'),
        ])

        updated = Locator.objects.get(pk=locator.pk)
        self.assertEqual(updated.title, 'NAME')

    def xtest_uses_hcard(self):
        locator = Locator.objects.create(url='https://example.com/1')

        update_locator_with_stuff(locator, [
            HEntry(
                'https://example.com/1', 'NAME', 'SUMMARY',
                HCard('AUTHOR', 'https://example.com/author')),
            ])

        updated = Locator.objects.get(pk=locator.pk)
        self.assertEqual(updated.author.native_name, 'AUTHOR')
        self.assertEqual(updated.author.profile.url, 'https://example.com/author')

