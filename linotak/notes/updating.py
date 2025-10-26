"""ROutines for updating information about external resources."""

import codecs
import re
from collections.abc import Callable
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..images.models import Image
from .models import Locator, LocatorImage
from .oembed import fetch_oembed
from .prescan import determine_encoding
from .scanner import HEntry, Img, Link, PageScanner, Title
from .signals import locator_post_scanned

# Images on the page smaller than this are ignored.
MIN_IMAGE_SIZE = 80


@transaction.atomic
def fetch_page_update_locator(locator, if_not_scanned_since):
    """Download and scan the web page referenced by this locator and update it.

    If there is an oEmbed resource for this page, scan that instead.

    Arguments:
        locator: Locator instance to scan
        if_not_scanned_since: datetime last known to be scanned,
            or None if presumed to be new

    The idea of the if_not_scanned_since parameter is you pass it as
    an argument when queuing a call to this function,
    and it prevents double scanning of the page.
    """
    if locator.scanned and (
        not if_not_scanned_since or if_not_scanned_since < locator.scanned
    ):
        return

    locator.scanned = timezone.now()  # This is rolled back if the scan fails.
    locator.save()
    # Setting it early should help prevent simultanous processing of the same page.

    # See if we can aquire an oEmbed resource instead:
    stuff = fetch_oembed(locator.url)
    if stuff is None:
        with requests.get(
            locator.url, stream=True, headers={"User-Agent": settings.NOTES_FETCH_AGENT}
        ) as r:
            stuff = parse_link_header(locator.url, r.headers.get("Link", ""))
            scanner = PageScanner(locator.url)

            feed_response_to_parser(r, scanner.feed)

            scanner.close()
            stuff += scanner.stuff

    update_locator_with_stuff(locator, stuff)
    locator.save()
    locator_post_scanned.send(Locator, locator=locator, stuff=stuff)
    return True


def feed_response_to_parser(
    response: requests.Response, feed_func: Callable[[str], None]
):
    """Pump character data in to the feed function from this response.

    This function attempts to do the right thing with characeter encodings etc.
    """

    # If content-type does not have a charset, Requests will guess the
    # encoding based on vibes, unless the content-type contains `text`
    # in which case it says `ISO-8859-1`. I would prefer to do the HTML5
    # thing in this case, which is examine the first part of the document
    # to find a META tag that gives the charset.

    encoding_unspecified = (
        not response.encoding
        or "text" in (content_type := response.headers.get("content-type"))
        and "charset" not in content_type
    )
    # TODO Anlyse the MIME type peoperly and skip processing for not-HTML.

    if encoding_unspecified:
        # Encoding not specified in headers, so we look for <meta charset> in the data.
        # But we can’t read the stream twice so we need to do some buffering.

        decode = None
        buf = b""
        for chunk in response.iter_content(None, decode_unicode=False):
            if decode:
                feed_func(decode(chunk))
            else:
                # We are scanning the first 1024 bytes to find `<meta charset=xxx>`.
                buf += chunk
                if len(buf) >= 1024:
                    encoding, certainty = determine_encoding(buf)
                    # We need an incremental decoder in case multibyte characters
                    # span the chunk boundaries.
                    codec_info = codecs.lookup(encoding)
                    decode = codec_info.incrementaldecoder().decode
                    feed_func(decode(buf))
                    buf = None
        if decode:
            feed_func(decode(b"", final=True))
        else:
            # Looks like the entire document was less than 1024 bytes.
            # Might still have a <meta charset> though.
            encoding, certainty = determine_encoding(buf)
            feed_func(buf.decode(encoding))
    else:
        # The builtin decoding by Requeists is probably fine.
        for chunk in response.iter_content(None, decode_unicode=True):
            feed_func(chunk)


COMMA = re.compile(r"\s*,\s*")
SEMICOLON = re.compile(r"\s*;\s*")
EQUALS = re.compile(r"\s*=\s*")
LINK_HREF = re.compile(r"^<(.*)>$")
QUOTED = re.compile(r'^"(.*)"$')


def parse_link_header(base_url, comma_separated):
    """Given a base URL and a Link header value, return list of Link instancecs."""
    links = []
    for link_spec in COMMA.split(comma_separated.strip()):
        if not link_spec:
            continue
        href_part, *parts = SEMICOLON.split(link_spec)
        href = urljoin(base_url, LINK_HREF.sub(r"\1", href_part))
        for part in parts:
            prop, val = EQUALS.split(part, 1)
            if prop == "rel":
                rel = QUOTED.sub(r"\1", val).split()
                break
        else:
            rel = None
        links.append(Link(rel, href))
    return links


def update_locator_with_stuff(locator, stuff):
    """Given stuff gathered about a page, update this locator.

    Does not save the locator.
    """
    titles = (
        []
    )  # Candidates for title of the form (WEIGHT, TITLE) where WEIGHT is a positive integer and TITLE is nonemoty.
    images = []  # Candidate images
    for thing in stuff:
        if isinstance(thing, Title):
            if thing.text:
                titles.append((1, thing.text))
        elif isinstance(thing, HEntry):
            if thing.name:
                titles.append((2, thing.name))
            if thing.summary:
                locator.text = thing.summary
            if thing.images:
                images += thing.images
        elif isinstance(thing, Img):
            images.append(thing)
    if titles:
        _, title = max(titles)
        if title:
            locator.title = title
    for img in images:
        if (
            img.width
            and img.width < MIN_IMAGE_SIZE
            or img.height
            and img.height < MIN_IMAGE_SIZE
        ):
            continue
        thing, is_new = LocatorImage.objects.get_or_create(
            locator=locator, image=image_of_img(img)
        )


def image_of_img(img):
    return Image.objects.get_from_img(img.src, img.type, img.width, img.height)
