"""Tests for the metnions app."""

from datetime import timedelta
from django.db import transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
import factory
import httpretty
from unittest.mock import patch

from ..notes.models import Locator
from ..notes.tests.factories import LocatorFactory, NoteFactory
from ..notes.scanner import Link

from .models import Receiver, Outgoing, handle_locator_scanned, notify_webmention_receiver
from . import tasks


class ReceiverFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Receiver

    url = factory.Sequence(lambda n: 'https://site%d.example.com/webmention' % n)


class OutgoingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Outgoing

    source = factory.SubFactory(NoteFactory)
    target = factory.SubFactory(LocatorFactory)
    receiver = factory.SubFactory(ReceiverFactory)


class TestHandleLocatorScanned(TestCase):
    """Test handle_locator_scanned."""

    def test_when_no_links_mark_outgoing_mentions_done(self):
        mention = Outgoing.objects.create(source=NoteFactory.create(), target=LocatorFactory.create())

        handle_locator_scanned(Locator, locator=mention.target, stuff=[])

        mention.refresh_from_db()
        self.assertFalse(mention.receiver)
        self.assertTrue(mention.discovered)

    def test_does_not_change_already_processed_mentions(self):
        then = timezone.now()
        mention = Outgoing.objects.create(source=NoteFactory.create(), target=LocatorFactory.create(), discovered=then)

        handle_locator_scanned(Locator, locator=mention.target, stuff=[])

        mention.refresh_from_db()
        self.assertFalse(mention.receiver)
        self.assertEqual(mention.discovered, then)

    def test_applies_first_link_found(self):
        mention = Outgoing.objects.create(source=NoteFactory.create(), target=LocatorFactory.create())

        handle_locator_scanned(Locator, locator=mention.target, stuff=[
            Link('webmention', 'https://example.com/1'),
            Link('webmention', 'https://example.com/2'),
        ])

        mention.refresh_from_db()
        self.assertEqual(mention.receiver.url, 'https://example.com/1')
        self.assertTrue(mention.discovered)


class TestHandleLocatorScannedTriggersNotification(TransactionTestCase):
    """Test handle_locator_scanned triggerss notification."""

    def test_queues_fetch_when_locator_created(self):
        """Test handle_locator_scanned queues fetch when receiver found."""
        mention = Outgoing.objects.create(source=NoteFactory.create(), target=LocatorFactory.create())

        with self.settings(MENTIONS_POST_NOTIFICATIONS=True), \
                patch.object(tasks, 'notify_outgoing_webmention_receiver') as notify_outgoing_webmention_receiver:
            with transaction.atomic():
                handle_locator_scanned(Outgoing, locator=mention.target, stuff=[
                    Link('webmention', 'https://example.com/1'),
                ])

                self.assertFalse(notify_outgoing_webmention_receiver.delay.called)
                # Not queued during the transaction to avoid race condition.

            notify_outgoing_webmention_receiver.delay.assert_called_once_with(mention.pk)


class TestNotifyReceiver(TestCase):

    def setUp(self):
        self.calls = []

    @httpretty.activate(allow_net_connect=False)
    def test_does_nothing_when_already_notified(self):
        then = timezone.now() + timedelta(days=-1)
        mention = OutgoingFactory.create(notified=then)

        notify_webmention_receiver(mention)

        mention.refresh_from_db()
        self.assertEqual(mention.notified, then)
        # Will complain if we try to make HTTP request.

    @httpretty.activate(allow_net_connect=False)
    def test_calls_webmention_endpoints_on_outgoing_mentions(self):
        mention = OutgoingFactory.create(
            source__series__name='alpha',
            source__published=timezone.now(),
            target__url='https://blog.example.com/2019/10/16',
            receiver__url='https://example.com/webmention-endpoint',
        )
        httpretty.register_uri(
            httpretty.POST, 'https://example.com/webmention-endpoint',
            body=self.response_callback,
        )

        with self.settings(NOTES_DOMAIN='notes.example.com'):
            notify_webmention_receiver(mention)

        self.assertEqual(len(self.calls), 1)
        query_params, parsed_body = self.calls[0]
        self.assertFalse(query_params)
        self.assertEqual(parsed_body['source'], ['https://alpha.notes.example.com/%s' % (mention.source.pk,)])
        self.assertEqual(parsed_body['target'], ['https://blog.example.com/2019/10/16'])
        mention.refresh_from_db()
        self.assertTrue(mention.notified)
        self.assertEqual(mention.response_status, 202)

    @httpretty.activate(allow_net_connect=False)
    def test_includes_querey_string_params_of_endpoint(self):
        mention = OutgoingFactory.create(
            receiver__url='https://example.com/webmention-endpoint?this=that',
        )
        httpretty.register_uri(
            httpretty.POST, 'https://example.com/webmention-endpoint',
            body=self.response_callback,
        )

        with self.settings(NOTES_DOMAIN='notes.example.com'):
            notify_webmention_receiver(mention)

        self.assertEqual(len(self.calls), 1)
        query_string, _ = self.calls[0]
        self.assertEqual(query_string, {'this': ['that']})

    def response_callback(self, request, uri, response_headers):
        self.calls.append((dict(request.querystring), request.parsed_body))
        return 202, response_headers, ''
