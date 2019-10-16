"""Tests for the metnions app."""

from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
import factory
import httpretty

from ..notes.models import Locator
from ..notes.tests.factories import LocatorFactory, NoteFactory
from ..notes.scanner import Link

from .models import Receiver, Outgoing, handle_locator_scanned, notify_outgoing_mention


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


class TestNotifyReceiver(TestCase):

    def setUp(self):
        self.calls = []

    @httpretty.activate(allow_net_connect=False)
    def test_does_nothing_when_already_notified(self):
        then = timezone.now() + timedelta(days=-1)
        mention = OutgoingFactory.create(notified=then)

        notify_outgoing_mention(mention)

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
            httpretty.GET, 'https://example.com/webmention-endpoint',
            body=self.response_callback,
        )

        with self.settings(NOTES_DOMAIN='notes.example.com'):
            notify_outgoing_mention(mention)

        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0]['source'], ['https://alpha.notes.example.com/%s' % (mention.source.pk,)])
        self.assertEqual(self.calls[0]['target'], ['https://blog.example.com/2019/10/16'])
        mention.refresh_from_db()
        self.assertTrue(mention.notified)
        self.assertEqual(mention.response_status, 202)

    @httpretty.activate(allow_net_connect=False)
    def test_includes_querey_string_params_of_endpoint(self):
        mention = OutgoingFactory.create(
            receiver__url='https://example.com/webmention-endpoint?this=that',
        )
        httpretty.register_uri(
            httpretty.GET, 'https://example.com/webmention-endpoint',
            body=self.response_callback,
        )

        with self.settings(NOTES_DOMAIN='notes.example.com'):
            notify_outgoing_mention(mention)

        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0]['this'], ['that'])

    def response_callback(self, request, uri, response_headers):
        self.calls.append(dict(request.querystring))
        return 202, response_headers, ''
