"""Tests for the metnions app."""

from datetime import timedelta
from django.db import transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
import factory
import httpretty
from unittest.mock import patch

from ..notes.models import Locator, Note
from ..notes.tests.factories import SeriesFactory, LocatorFactory, NoteFactory
from ..notes.scanner import Link, HEntry

from .forms import IncomingForm
from .models import (
    Receiver,
    LocatorReceiver,
    Outgoing,
    Incoming,
    handle_note_post_save,
    handle_locator_post_scanned,
    notify_webmention_receiver,
)
from . import tasks


class ReceiverFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Receiver

    url = factory.Sequence(lambda n: "https://site%d.example.com/webmention" % n)


class OutgoingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Outgoing

    source = factory.SubFactory(NoteFactory)
    target = factory.SubFactory(LocatorFactory)

    @factory.post_generation
    def receiver(obj, created, extracted, **kwargs):
        receiver = (
            extracted if extracted else ReceiverFactory(**kwargs) if kwargs else None
        )
        if receiver:
            LocatorReceiver.objects.create(locator=obj.target, receiver=receiver)


class TestHandleNotePostSave(TestCase):
    """Test handle_note_post_save."""

    def setUp(self):
        self.note = NoteFactory()
        self.target_url = "https://example.com/blog/1"
        self.note.add_subject(self.target_url)

    def test_does_nothing_if_raw(self):
        # No mentions should already be created but delete them anyway for clarity.
        Outgoing.objects.all().delete()

        handle_note_post_save(Note, self.note, True, True)

        self.assertFalse(Outgoing.objects.filter(target__url=self.target_url).exists())

    def test_does_nothing_if_unpublished(self):
        # No mentions should already be created but delete them anyway for clarity.
        Outgoing.objects.all().delete()

        handle_note_post_save(Note, self.note, False, False)

        self.assertFalse(Outgoing.objects.filter(target__url=self.target_url).exists())

    def test_creates_mention_if_published(self):
        # No mentions should already be created but delete them anyway for clarity.
        Outgoing.objects.all().delete()

        self.note.published = timezone.now()
        self.note.save()  # This fires the signal that calls the handler!

        outgoing = Outgoing.objects.get(target__url=self.target_url)
        self.assertEqual(outgoing.source, self.note)
        self.assertEqual(outgoing.target.url, self.target_url)


class TestHandleLocatorScanned(TestCase):
    """Test handle_locator_post_scanned.

    This is used (a) to find webmention enpoint of target of outgoint mention,
    and (b) when looking at source of incoming webmention.
    """

    def test_sets_recevier_to_null_when_no_link(self):
        locator = LocatorFactory()

        handle_locator_post_scanned(Locator, locator=locator, stuff=[])

        result = LocatorReceiver.objects.get(locator=locator)
        self.assertFalse(result.receiver)

    def test_uses_first_link_found(self):
        locator = LocatorFactory()

        handle_locator_post_scanned(
            Locator,
            locator=locator,
            stuff=[
                Link("other", "https://example.com/0"),
                Link("webmention", "https://example.com/1"),
                Link("webmention", "https://example.com/2"),
            ],
        )

        result = LocatorReceiver.objects.get(locator=locator)
        self.assertEqual(result.receiver.url, "https://example.com/1")

    def test_uses_link_from_entry_matching_page(self):
        locator = LocatorFactory()

        handle_locator_post_scanned(
            Locator,
            locator=locator,
            stuff=[
                HEntry(
                    None,
                    "Discovery Test #5",
                    classes=["post-container", "h-entry"],
                    links=[
                        Link(
                            "webmention",
                            "https://example.com/test/5/webmention",
                            text="Webmention endpoint",
                        )
                    ],
                ),
            ],
        )

        result = LocatorReceiver.objects.get(locator=locator)
        self.assertEqual(
            result.receiver and result.receiver.url,
            "https://example.com/test/5/webmention",
        )

    def test_updates_existing(self):
        locator = LocatorFactory()
        LocatorReceiver.objects.create(locator=locator, receiver=ReceiverFactory())

        handle_locator_post_scanned(
            Locator,
            locator=locator,
            stuff=[
                Link("webmention", "https://example.com/new"),
            ],
        )

        result = LocatorReceiver.objects.get(locator=locator)
        self.assertEqual(result.receiver.url, "https://example.com/new")

    def test_updates_intent_of_incoming_mention(self):
        locator = LocatorFactory()
        note = NoteFactory(series__name="spoo")
        incoming = Incoming.objects.create(
            source=locator,
            target=note,
            target_url=f"https://spoo.example.com/{note.pk}",
        )

        with self.settings(NOTES_DOMAIN="example.com"):
            handle_locator_post_scanned(
                Locator,
                locator=locator,
                stuff=[
                    HEntry(
                        None,
                        "Liiiike",
                        classes=["h-entry"],
                        links=[
                            Link(
                                None,
                                f"https://spoo.example.com/{note.pk}",
                                classes=["u-like-of"],
                            )
                        ],
                    ),
                ],
            )

        incoming.refresh_from_db()
        self.assertEqual(incoming.intent, incoming.LIKE)


class TestHandleLocatorScannedTriggersNotification(TransactionTestCase):
    """Test handle_locator_post_scanned triggers notification."""

    def test_queues_fetch_when_locator_scanned_in_published_note_after_mention_created(
        self,
    ):
        """Test handle_locator_post_scanned queues fetch when receiver found."""
        mention = Outgoing.objects.create(
            source=NoteFactory(published=timezone.now()), target=LocatorFactory()
        )

        with self.settings(MENTIONS_POST_NOTIFICATIONS=True), patch.object(
            tasks, "notify_outgoing_webmention_receiver"
        ) as notify_outgoing_webmention_receiver:
            with transaction.atomic():
                handle_locator_post_scanned(
                    Outgoing,
                    locator=mention.target,
                    stuff=[
                        Link("webmention", "https://example.com/1"),
                    ],
                )

                self.assertFalse(notify_outgoing_webmention_receiver.delay.called)
                # Not queued during the transaction to avoid race condition.

            notify_outgoing_webmention_receiver.delay.assert_called_once_with(
                mention.pk
            )
            mention.refresh_from_db()
            self.assertEqual(mention.receiver, mention.target.mentions_info.receiver)

    def test_queues_fetch_when_note_published_after_locator_scanned(self):
        source = NoteFactory()
        target = LocatorFactory()
        source.add_subject(target)
        LocatorReceiver.objects.create(
            locator=target, receiver=ReceiverFactory()
        )  # Simulate relevant part of scanning

        with self.settings(MENTIONS_POST_NOTIFICATIONS=True), patch.object(
            tasks, "notify_outgoing_webmention_receiver"
        ) as notify_outgoing_webmention_receiver:
            with transaction.atomic():
                source.published = timezone.now()
                source.save()

                self.assertFalse(notify_outgoing_webmention_receiver.delay.called)
                # Not queued during the transaction to avoid race condition.

            notify_outgoing_webmention_receiver.delay.assert_called_once()
            (mention_pk,) = notify_outgoing_webmention_receiver.delay.call_args.args
            mention = Outgoing.objects.get(pk=mention_pk)
            self.assertEqual(mention.receiver, mention.target.mentions_info.receiver)


class TestNotifyReceiver(TestCase):
    def setUp(self):
        self.calls = []

    @httpretty.activate(allow_net_connect=False)
    def test_does_nothing_when_already_notified(self):
        then = timezone.now() + timedelta(days=-1)
        mention = OutgoingFactory(notified=then)

        notify_webmention_receiver(mention)

        mention.refresh_from_db()
        self.assertEqual(mention.notified, then)
        # Will complain if we try to make HTTP request.

    @httpretty.activate(allow_net_connect=False)
    def test_calls_webmention_endpoints_on_outgoing_mentions(self):
        mention = OutgoingFactory(
            source__series__name="alpha",
            source__published=timezone.now(),
            target__url="https://blog.example.com/2019/10/16",
            receiver__url="https://example.com/webmention-endpoint",
        )
        httpretty.register_uri(
            httpretty.POST,
            "https://example.com/webmention-endpoint",
            body=self.response_callback,
        )

        with self.settings(NOTES_DOMAIN="notes.example.com"):
            notify_webmention_receiver(mention)

        self.assertEqual(len(self.calls), 1)
        query_params, parsed_body = self.calls[0]
        self.assertFalse(query_params)
        self.assertEqual(
            parsed_body["source"],
            ["https://alpha.notes.example.com/%s" % (mention.source.pk,)],
        )
        self.assertEqual(parsed_body["target"], ["https://blog.example.com/2019/10/16"])
        mention.refresh_from_db()
        self.assertTrue(mention.notified)
        self.assertEqual(mention.response_status, 202)

    @httpretty.activate(allow_net_connect=False)
    def test_includes_querey_string_params_of_endpoint(self):
        mention = OutgoingFactory(
            receiver__url="https://example.com/webmention-endpoint?this=that",
        )
        httpretty.register_uri(
            httpretty.POST,
            "https://example.com/webmention-endpoint",
            body=self.response_callback,
        )

        with self.settings(NOTES_DOMAIN="notes.example.com"):
            notify_webmention_receiver(mention)

        self.assertEqual(len(self.calls), 1)
        query_string, _ = self.calls[0]
        self.assertEqual(query_string, {"this": ["that"]})

    def response_callback(self, request, uri, response_headers):
        self.calls.append((dict(request.querystring), request.parsed_body))
        return 202, response_headers, ""


class TestIncomingForm(TestCase):
    def test_doesnt_create_source_locator_if_cannot_find_target_note(self):
        source_url = "https://example.com/blog/1"
        target_url = "https://alpha.notes.example.org/blah/blah"
        form = IncomingForm(
            {
                "source": source_url,
                "target": target_url,
            }
        )
        self.assertTrue(form.is_valid())

        with self.settings(NOTES_DOMAIN="notes.example.org"):
            result = form.save(http_user_agent="Agent/69 (like Netscape Navigator)")

        self.assertEqual(result.source_url, source_url)
        self.assertEqual(result.target_url, target_url)
        self.assertEqual(result.user_agent, "Agent/69 (like Netscape Navigator)")
        self.assertFalse(result.source)
        self.assertFalse(result.target)

    def test_doesnt_process_note_if_URL_origin_doesnt_match(self):
        series = SeriesFactory(name="alpha")
        note = NoteFactory(series=series)

        source_url = "https://example.com/blog/1"
        target_url = "https://wrong.example.org/tagged/froth/page5/%s" % note.pk
        form = IncomingForm(
            {
                "source": source_url,
                "target": target_url,
            }
        )
        self.assertTrue(form.is_valid())

        with self.settings(NOTES_DOMAIN="notes.example.org"):
            result = form.save(http_user_agent="Agent/69 (like Netscape Navigator)")

        self.assertEqual(result.source_url, source_url)
        self.assertEqual(result.target_url, target_url)
        self.assertEqual(result.user_agent, "Agent/69 (like Netscape Navigator)")
        self.assertFalse(result.source)
        self.assertFalse(result.target)

    def test_creates_source_locator_and_links_to_existing_note(self):
        series = SeriesFactory(name="alpha")
        note = NoteFactory(series=series)

        source_url = "https://example.com/blog/1"
        target_url = "https://alpha.notes.example.org/tagged/froth/page5/%s" % note.pk
        form = IncomingForm(
            {
                "source": source_url,
                "target": target_url,
            }
        )
        self.assertTrue(form.is_valid())

        with self.settings(NOTES_DOMAIN="notes.example.org"):
            result = form.save(http_user_agent="Agent/69")

        self.assertEqual(result.source.url, source_url)
        self.assertEqual(result.target, note)

    def test_collapses_matching_notifications(self):
        series = SeriesFactory(name="alpha")
        note = NoteFactory(series=series)
        source_url = "https://example.com/blog/1"
        target_url = "https://alpha.notes.example.org/tagged/froth/page5/%s" % note.pk
        then = timezone.now() - timedelta(minutes=5)
        existing = Incoming.objects.create(
            source_url=source_url, target_url=target_url, received=then
        )
        form = IncomingForm(
            {
                "source": source_url,
                "target": target_url,
            }
        )
        self.assertTrue(form.is_valid())

        now = timezone.now()
        with self.settings(NOTES_DOMAIN="notes.example.org"), patch.object(
            timezone, "now", return_value=now
        ):
            result = form.save(http_user_agent="Agent/69")

        existing.refresh_from_db()
        self.assertEqual(result, existing)
        self.assertEqual(result.received, now)  # Has updated date to most recent

    # TODO. In future this test will only collapse unprocessed duplicates...


class TestWebmentionEndpoint(TestCase):
    def test_processes_form_when_URLs_posted(self):
        series = SeriesFactory(name="alpha")
        note = NoteFactory(series=series)

        response = self.client.post(
            reverse("webmention"),
            {
                "source": "http://example.com/blog/1",
                "target": "https://alpha.notes.example.org/%d" % note.pk,
            },
        )

        incoming = Incoming.objects.get(source_url="http://example.com/blog/1")
        self.assertEqual(
            incoming.target_url, "https://alpha.notes.example.org/%d" % note.pk
        )
        # Does NOT redirect, but shows template instead:
        self.assertEqual(response.status_code, 201)  # Created
        self.assertEqual(response["Location"], incoming.get_absolute_url())
