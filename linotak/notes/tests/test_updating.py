"""Test updating."""

from base64 import b64encode
from datetime import timedelta
from unittest.mock import patch

import httpretty
from django.test import TestCase
from django.utils import timezone

from ...images.models import Image
from .. import updating
from ..models import Locator, LocatorImage
from ..scanner import HCard, HEntry, Img, Link, Title
from ..signals import locator_post_scanned
from ..updating import (
    fetch_page_update_locator,
    image_of_img,
    parse_link_header,
    update_locator_with_stuff,
)


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
        self.assert_doesnt_request_data_when(
            locator_scanned=more_recently, if_not_scanned_since=then
        )

    @httpretty.activate(allow_net_connect=False)
    def test_doesnt_request_data_when_scanned_since_new(self):
        then = timezone.now() - timedelta(days=8)
        self.assert_doesnt_request_data_when(
            locator_scanned=then, if_not_scanned_since=None
        )

    @httpretty.activate(allow_net_connect=False)
    def test_follows_redirects(self):
        locator = Locator.objects.create(url="https://example.com/1")
        with (
            patch.object(updating, "PageScanner") as cls,
            patch.object(updating, "update_locator_with_stuff") as mock_update,
            patch.object(locator_post_scanned, "send") as locator_post_scanned_send,
            patch.object(updating, "fetch_oembed") as fetch_oembed,
        ):
            fetch_oembed.return_value = None
            page_scanner = cls.return_value
            page_scanner.stuff = ["**STUFF**"]

            httpretty.register_uri(
                httpretty.GET,
                "https://example.com/1",
                body="REDIRECT",
                status=302,
                adding_headers={"Location": "https://example.com/2"},
            )
            httpretty.register_uri(
                httpretty.GET,
                "https://example.com/2",
                body="CONTENT OF PAGE",
            )

            result = fetch_page_update_locator(locator, if_not_scanned_since=None)

            self.assertTrue(result)
            cls.assert_called_with("https://example.com/1")
            page_scanner.feed.assert_called_with("CONTENT OF PAGE")
            page_scanner.close.assert_called_with()

            locator_post_scanned_send.assert_called_once_with(
                Locator, locator=locator, stuff=["**STUFF**"]
            )
            mock_update.assert_called_once_with(locator, ["**STUFF**"])

            updated = Locator.objects.get(pk=locator.pk)
            self.assertTrue(updated.scanned)

    @httpretty.activate(allow_net_connect=False)
    def test_doesnt_fetch_page_when_oembed_available(self):
        # Given a locator that has never been scanned …
        locator = Locator.objects.create(url="https://example.com/1")
        # And an oembed resource exists for this URL …
        with (
            patch.object(updating, "PageScanner") as cls,
            patch.object(updating, "update_locator_with_stuff") as mock_update,
            patch.object(locator_post_scanned, "send") as locator_post_scanned_send,
            patch.object(updating, "fetch_oembed") as fetch_oembed,
        ):
            fetch_oembed.return_value = ["**OEMBED*STUFF**"]

            result = fetch_page_update_locator(locator, if_not_scanned_since=None)

            self.assertTrue(result)
            fetch_oembed.assert_called_once_with("https://example.com/1")
            self.assertFalse(cls.called)  # Did not attempt page scanner

            locator_post_scanned_send.assert_called_once_with(
                Locator, locator=locator, stuff=["**OEMBED*STUFF**"]
            )
            mock_update.assert_called_once_with(locator, ["**OEMBED*STUFF**"])

            locator.refresh_from_db()
            self.assertTrue(locator.scanned)

    def assert_requests_data_when(self, locator_scanned, if_not_scanned_since):
        locator = Locator.objects.create(
            url="https://example.com/1", scanned=locator_scanned
        )
        with (
            patch.object(updating, "PageScanner") as cls,
            patch.object(updating, "update_locator_with_stuff") as mock_update,
            patch.object(locator_post_scanned, "send") as locator_post_scanned_send,
            patch.object(updating, "fetch_oembed") as fetch_oembed,
        ):
            fetch_oembed.return_value = None
            page_scanner = cls.return_value
            page_scanner.stuff = ["**STUFF**"]
            httpretty.register_uri(
                httpretty.GET,
                "https://example.com/1",
                body="CONTENT OF PAGE",
            )

            result = fetch_page_update_locator(
                locator, if_not_scanned_since=if_not_scanned_since
            )

            self.assertTrue(result)
            cls.assert_called_with("https://example.com/1")
            page_scanner.feed.assert_called_with("CONTENT OF PAGE")
            page_scanner.close.assert_called_with()

            locator_post_scanned_send.assert_called_once_with(
                Locator, locator=locator, stuff=["**STUFF**"]
            )
            mock_update.assert_called_once_with(locator, ["**STUFF**"])

            updated = Locator.objects.get(pk=locator.pk)
            self.assertTrue(updated.scanned)

    def assert_doesnt_request_data_when(self, locator_scanned, if_not_scanned_since):
        locator = Locator.objects.create(
            url="https://example.com/1", scanned=locator_scanned
        )
        with (
            patch.object(updating, "PageScanner") as cls,
            patch.object(updating, "fetch_oembed") as fetch_oembed,
        ):
            # Httpretty should complain if any call is made because none is registered.

            result = fetch_page_update_locator(
                locator, if_not_scanned_since=if_not_scanned_since
            )

            self.assertFalse(result)
            self.assertFalse(fetch_oembed.called)
            self.assertFalse(cls.called)


class TestFetchPageLinks(TestCase):
    @httpretty.activate(allow_net_connect=False)
    def test_returns_links_as_stuff(self):
        locator = Locator.objects.create(url="https://example.com/1")
        with (
            patch.object(updating, "PageScanner") as cls,
            patch.object(updating, "update_locator_with_stuff") as mock_update,
        ):
            page_scanner = cls.return_value
            httpretty.register_uri(
                httpretty.GET,
                "https://example.com/1",
                adding_headers={
                    "Link": '</test/1/webmention>; rel=webmention, </2>; rel=next, </>; rel="top"; hreflang="en"'
                },
            )
            page_scanner.stuff = ["**STUFF**"]

            fetch_page_update_locator(locator, if_not_scanned_since=None)

            mock_update.assert_called_once_with(
                locator,
                [
                    Link("webmention", "https://example.com/test/1/webmention"),
                    Link("next", "https://example.com/2"),
                    Link("top", "https://example.com/"),
                    "**STUFF**",
                ],
            )

    def test_parses_webmention_2_link_header(self):
        result = parse_link_header(
            "https://webmention.rocks/test/2",
            "<https://webmention.rocks/test/2/webmention?head=true>; rel=webmention",
        )
        self.assertEqual(
            result,
            [
                Link(
                    "webmention", "https://webmention.rocks/test/2/webmention?head=true"
                )
            ],
        )

    def test_parses_webmention_10_link_header(self):
        result = parse_link_header(
            "https://webmention.rocks/test/10",
            '<https://webmention.rocks/test/10/webmention?head=true>; rel="webmention somethingelse"',
        )
        self.assertEqual(
            result,
            [
                Link(
                    {"webmention", "somethingelse"},
                    "https://webmention.rocks/test/10/webmention?head=true",
                )
            ],
        )


class TestUpdateLocatorWithStuff(TestCase):
    """Test update_locator_with_stuff."""

    @classmethod
    def setUpTestData(cls):
        cls.locator = Locator.objects.create(url="https://example.com/1")

    def test_uses_title(self):
        update_locator_with_stuff(self.locator, [Title("TITLE OF PAGE")])

        self.assertEqual(self.locator.title, "TITLE OF PAGE")

    def test_uses_hentry(self):
        update_locator_with_stuff(
            self.locator,
            [
                HEntry(
                    "https://example.com/1",
                    "NAME",
                    "SUMMARY",
                    HCard("AUTHOR", "https://example.com/author"),
                ),
            ],
        )

        self.assertEqual(self.locator.title, "NAME")
        self.assertEqual(self.locator.text, "SUMMARY")

    def test_uses_hentry_over_title(self):
        update_locator_with_stuff(
            self.locator,
            [
                HEntry(
                    "https://example.com/1",
                    "NAME",
                    "SUMMARY",
                    HCard("AUTHOR", "https://example.com/author"),
                ),
                Title("OTHER TITLE"),
            ],
        )

        self.assertEqual(self.locator.title, "NAME")

    def test_uses_toplevel_images(self):
        update_locator_with_stuff(
            self.locator,
            [
                Img("https://images.example.com/42"),
            ],
        )

        self.assertEqual(
            self.locator.images.all()[0].data_url, "https://images.example.com/42"
        )

    def test_drops_small_images(self):
        update_locator_with_stuff(
            self.locator,
            [
                Img("https://images.example.com/42", width=75, height=75),
            ],
        )

        self.assertFalse(self.locator.images.all())

    def test_copies_media_type_and_size(self):
        update_locator_with_stuff(
            self.locator,
            [
                Img(
                    "https://images.example.com/42",
                    type="image/jpeg",
                    width=1001,
                    height=997,
                ),
            ],
        )

        self.assertEqual(self.locator.images.all().count(), 1)
        actual = self.locator.images.all()[0]
        self.assertEqual(actual.data_url, "https://images.example.com/42")
        self.assertEqual(actual.media_type, "image/jpeg")
        self.assertEqual(actual.width, 1001)
        self.assertEqual(actual.height, 997)

    def test_doesnt_clobber_existing_metadata(self):
        LocatorImage.objects.create(
            locator=self.locator,
            image=Image.objects.create(
                data_url="https://images.example.com/69",
                media_type="application/octet-stream",
                width=1280,
                height=960,
            ),
        )
        update_locator_with_stuff(
            self.locator,
            [
                Img("https://images.example.com/69", type="image/jpeg"),
            ],
        )

        actual = self.locator.images.all()[0]
        self.assertEqual(actual.media_type, "image/jpeg")
        self.assertEqual(actual.width, 1280)
        self.assertEqual(actual.height, 960)

    def test_uses_hentry_images(self):
        update_locator_with_stuff(
            self.locator,
            [
                HEntry(images=[Img("https://images.example.com/42")]),
            ],
        )

        self.assertEqual(
            self.locator.images.all()[0].data_url, "https://images.example.com/42"
        )

    def xtest_uses_hcard(self):
        update_locator_with_stuff(
            self.locator,
            [
                HEntry(
                    "https://example.com/1",
                    "NAME",
                    "SUMMARY",
                    HCard("AUTHOR", "https://example.com/author"),
                ),
            ],
        )

        self.assertEqual(self.locator.author.native_name, "AUTHOR")
        self.assertEqual(self.locator.author.profile.url, "https://example.com/author")


class TestImageOfImg(TestCase):
    def test_usual_case(self):
        img = Img("http://an.example/img.png", "image/png", width=1080, height=720)

        result = image_of_img(img)

        self.assertEqual(result.data_url, "http://an.example/img.png")
        self.assertEqual(result.media_type, "image/png")
        self.assertEqual(result.width, 1080)
        self.assertEqual(result.height, 720)

    def test_unpacks_data_url(self):
        img = Img(
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg==",
            width=80,
            height=80,
        )

        result = image_of_img(img)

        # Then it immediately uses the data from the URL as the cached data …
        self.assertTrue(result.cached_data)
        self.assertTrue(result.retrieved)
        self.assertTrue(result.etag)
        self.assertEqual(result.media_type, "image/png")
        # And creates an etag URL …
        self.assertEqual(
            result.data_url,
            "tag:alleged.org.uk,2025:etag:" + b64encode(result.etag).decode(),
        )
        # Gets width from real image.
        self.assertEqual(result.width, 5)
        self.assertEqual(result.height, 5)
