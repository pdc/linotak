"""Tests for fetching oEmbed resourecs."""

import json
from unittest.mock import patch

import httpretty
from django.test import TestCase

from ..oembed import (
    OEmbedEndpoint,
    fetch_oembed,
    load_endpoints,
    re_from_url_globs,
    stuffs_from_oembed,
    template_from_oembed,
)
from ..scanner import HCard, Img, Title


class TestReFromUrlPatterns(TestCase):
    def test_combines_several_patterns_into_one_re(self):
        result = re_from_url_globs(
            [
                "https://albion.example/foo",
                "https://narnia.example/bar",
            ]
        )

        self.assertTrue(result.match("https://albion.example/foo"))
        self.assertTrue(result.match("https://narnia.example/bar"))

        self.assertTrue(result.match("https://albion.example/fooooo"))
        self.assertFalse(result.match("https://narnia.example/baz"))
        self.assertFalse(result.match("https://albion.example/bar"))
        self.assertFalse(result.match("https://lyonesse.example/foo"))
        self.assertFalse(result.match("http://narnia.example/bar"))

    def test_handles_wildcard_at_path_end(self):
        result = re_from_url_globs(["https://albion.example/foo/*"])

        self.assertTrue(result.match("https://albion.example/foo/bar"))
        self.assertTrue(result.match("https://albion.example/foo/bar/baz"))

    def test_handles_wildcard_in_path(self):
        result = re_from_url_globs(["https://albion.example/*/foo"])

        self.assertTrue(result.match("https://albion.example/bar/foo"))
        self.assertTrue(result.match("https://albion.example/bar/baz/foo"))

    def test_handles_wildcard_path(self):
        result = re_from_url_globs(["https://albion.example/*"])

        self.assertTrue(result.match("https://albion.example/foo/bar"))
        self.assertTrue(result.match("https://albion.example/"))

    def test_handles_wildcard_subromain(self):
        result = re_from_url_globs(["https://*.albion.example/foo"])

        self.assertTrue(result.match("https://squamous.albion.example/foo"))
        self.assertTrue(result.match("https://albion.example/foo"))


class TestTemplateFromAlmostTemplate(TestCase):
    def test_usually_adds_standard_query_params(self):
        result = template_from_oembed("http://flickr.com/services/oembed")

        self.assertEqual(
            result.expand(
                url="http://flickr.com/photos/bees/2362225867/",
                format="json",
                maxwidth="300",
                maxheight="400",
            ),
            "http://flickr.com/services/oembed?url=http%3A%2F%2Fflickr.com%2Fphotos%2Fbees%2F2362225867%2F&maxwidth=300&maxheight=400&format=json",
        )

    def test_allows_for_format_being_part_of_path(self):
        result = template_from_oembed("http://flickr.com/services/oembed.{format}")

        self.assertEqual(
            result.expand(
                url="http://flickr.com/photos/bees/2362225867/",
                format="json",
            ),
            "http://flickr.com/services/oembed.json?url=http%3A%2F%2Fflickr.com%2Fphotos%2Fbees%2F2362225867%2F",
        )


# Downloaded 2025-02-23
FLICKR_ENDPOINT = {
    "schemes": [
        "http://*.flickr.com/photos/*",
        "http://flic.kr/p/*",
        "http://flic.kr/s/*",
        "https://*.flickr.com/photos/*",
        "https://flic.kr/p/*",
        "https://flic.kr/s/*",
        "https://*.*.flickr.com/*/*",
        "http://*.*.flickr.com/*/*",
    ],
    "url": "https://www.flickr.com/services/oembed/",
    "discovery": True,
}

FLICKR_PROVIDER = {
    "provider_name": "Flickr",
    "provider_url": "https://www.flickr.com/",
    "endpoints": [FLICKR_ENDPOINT],
}

FLICKR_OEMBED = {
    "type": "photo",
    "flickr_type": "photo",
    "title": "Bacon Lollys",
    "author_name": "\u202e\u202d\u202cbees\u202c",
    "author_url": "https://www.flickr.com/photos/bees/",
    "width": 1024,
    "height": 768,
    "url": "https://live.staticflickr.com/3040/2362225867_4a87ab8baf_b.jpg",
    "web_page": "https://www.flickr.com/photos/bees/2362225867/",
    "thumbnail_url": "https://live.staticflickr.com/3040/2362225867_4a87ab8baf_q.jpg",
    "thumbnail_width": 150,
    "thumbnail_height": 150,
    "web_page_short_url": "https://flic.kr/p/4AK2sc",
    "license": "All Rights Reserved",
    "license_id": 0,
    "html": '<a data-flickr-embed="true" href="https://www.flickr.com/photos/bees/2362225867/" title="Bacon Lollys by \u202e\u202d\u202cbees\u202c, on Flickr"><img src="https://live.staticflickr.com/3040/2362225867_4a87ab8baf_b.jpg" width="1024" height="768" alt="Bacon Lollys"></a><script async src="https://embedr.flickr.com/assets/client-code.js" charset="utf-8"></script>',
    "version": "1.0",
    "cache_age": 3600,
    "provider_name": "Flickr",
    "provider_url": "https://www.flickr.com/",
}

YOUTUBE_ENDPOINT = {
    "schemes": [
        "https://*.youtube.com/watch*",
        "https://*.youtube.com/v/*",
        "https://youtu.be/*",
        "https://*.youtube.com/playlist?list=*",
        "https://youtube.com/playlist?list=*",
        "https://*.youtube.com/shorts*",
        "https://youtube.com/shorts*",
        "https://*.youtube.com/embed/*",
        "https://*.youtube.com/live*",
        "https://youtube.com/live*",
    ],
    "url": "https://www.youtube.com/oembed",
    "discovery": True,
}


def example_endpoint(name="foo", path="/"):
    return {
        "schemes": [
            f"https://*.{name}.example{path}*",
            f"https://{name}.example{path}*",
            f"http://*.{name}.example{path}*",
            f"http://{name}.example{path}*",
        ],
        "url": f"https://{name}.example/oembed",
        "discovery": True,
    }


class TestOembedEndpoint(TestCase):
    def test_can_be_created_from_providers_endpoint(self):
        input = FLICKR_ENDPOINT

        result = OEmbedEndpoint.from_json(input)

        self.assertEqual(
            result.url_for("http://flickr.com/photos/bees/2362225867/"),
            "https://www.flickr.com/services/oembed/?url=http%3A%2F%2Fflickr.com%2Fphotos%2Fbees%2F2362225867%2F&format=json",
        )
        self.assertFalse(result.url_for("https://www.youtube.com/v/123456"))

    def test_silently_drops_endpoints_lacking_urls(self):
        input = {"url": "https://www.beautiful.ai/api/oembed", "discovery": True}

        self.assertFalse(OEmbedEndpoint.from_json(input))


class TestStuffFromOEmbed(TestCase):
    def test_can_decode_youtube(self):
        # Fetched 2025-01
        input = {
            "title": "How was it made? Kiln-casting a glass sculpture | Colin Reid",
            "author_name": "Victoria and Albert Museum",
            "author_url": "https://www.youtube.com/@vamuseum",
            "type": "video",
            "height": 113,
            "width": 200,
            "version": "1.0",
            "provider_name": "YouTube",
            "provider_url": "https://www.youtube.com/",
            "thumbnail_height": 360,
            "thumbnail_width": 480,
            "thumbnail_url": "https://i.ytimg.com/vi/PsuI0guxFd4/hqdefault.jpg",
            "html": "\u003ciframe width=\u0022200\u0022 height=\u0022113\u0022 src=\u0022https://www.youtube.com/embed/PsuI0guxFd4?feature=oembed\u0022 frameborder=\u00220\u0022 allow=\u0022accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share\u0022 referrerpolicy=\u0022strict-origin-when-cross-origin\u0022 allowfullscreen title=\u0022How was it made? Kiln-casting a glass sculpture | Colin Reid\u0022\u003e\u003c/iframe\u003e",
        }

        result = stuffs_from_oembed(input)

        self.assertIn(
            Title("How was it made? Kiln-casting a glass sculpture | Colin Reid"),
            result,
        )
        self.assertIn(
            HCard("Victoria and Albert Museum", "https://www.youtube.com/@vamuseum"),
            result,
        )
        self.assertIn(
            Img(
                "https://i.ytimg.com/vi/PsuI0guxFd4/hqdefault.jpg",
                width=480,
                height=360,
                classes=["thumbnail"],
            ),
            result,
        )


class TestFetchOEmbed(TestCase):
    @httpretty.activate(allow_net_connect=False)
    def test_fetches_oembed_when_matches(self):
        # Given Flickr provides an oEmbed resource…
        httpretty.register_uri(
            httpretty.GET,
            "https://www.flickr.com/services/oembed/?url=http%3A%2F%2Fflickr.com%2Fphotos%2Fbees%2F2362225867%2F&format=json",
            match_querystring=True,
            body=json.dumps(FLICKR_OEMBED),
        )

        # When we request information about a Flickr URL …
        with patch("linotak.notes.oembed.get_endpoints") as get_endpoints:
            get_endpoints.return_value = [
                OEmbedEndpoint.from_json(example_endpoint("bunnies")),
                OEmbedEndpoint.from_json(FLICKR_ENDPOINT),
                OEmbedEndpoint.from_json(example_endpoint("snails")),
            ]
            result = fetch_oembed("http://flickr.com/photos/bees/2362225867/")

        # Then we get stuff we can use in links.
        self.assertIn(
            Img(
                "https://live.staticflickr.com/3040/2362225867_4a87ab8baf_b.jpg",
                width=1024,
                height=768,
                classes=["photo"],
            ),
            result,
        )

    @httpretty.activate(allow_net_connect=False)
    def test_returns_false_when_no_oembed(self):
        # When we request information about a non-matching URL …
        with patch("linotak.notes.oembed.get_endpoints") as get_endpoints:
            get_endpoints.return_value = [
                OEmbedEndpoint.from_json(example_endpoint("bunnies")),
                OEmbedEndpoint.from_json(FLICKR_ENDPOINT),
                OEmbedEndpoint.from_json(example_endpoint("snails")),
            ]
            result = fetch_oembed("http://kittens.example/photos/69")

        # Then no stuff is returned.
        self.assertFalse(result)


class TestLoadEndpoints(TestCase):
    @httpretty.activate(allow_net_connect=False)
    def test_fetches_from_url_and_parses(self):
        # Given an online JSON resource containing the provider definition for Flickr …
        httpretty.register_uri(
            httpretty.GET,
            "http://oembed.example/providers.json",
            body=json.dumps(
                [
                    FLICKR_PROVIDER,
                    {
                        "provider_name": "Beautiful.AI",
                        "provider_url": "https://www.beautiful.ai/",
                        "endpoints": [
                            {
                                "url": "https://www.beautiful.ai/api/oembed",
                                "discovery": True,
                            }
                        ],
                    },
                ]
            ),
        )

        # When loading those endpoints …
        with self.settings(OEMBED_PROVIDERS_URL="http://oembed.example/providers.json"):
            result = load_endpoints()

        # Then the flickr endpoint is recognized and the broken one skipped.
        self.assertCountEqual(result, [OEmbedEndpoint.from_json(FLICKR_ENDPOINT)])
