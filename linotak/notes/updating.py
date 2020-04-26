"""ROutines for updating information about external resources."""

from django.db import transaction
from django.utils import timezone
import re
import requests
from urllib.parse import urljoin

from ..images.models import Image
from .models import Locator, LocatorImage
from .scanner import PageScanner, Title, HEntry, Img, Link
from .signals import locator_post_scanned


@transaction.atomic
def fetch_page_update_locator(locator, if_not_scanned_since):
    """Download and scan the web page thus locator references and update it."

    Arguments:
        locator: Locator instance to scan
        if_not_scanned_since: datetime last known to be scanned,
            or None if presumed to be new

    The idea of the if_not_scanned_since parameter is you pass it as
    an argument when queuing a call to this function,
    and it prevents double scanning of the page.
    """
    if locator.scanned and (not if_not_scanned_since or if_not_scanned_since < locator.scanned):
        return

    locator.scanned = timezone.now()  # This is rolled back if the scan fails.
    # Setting it early should help prevent simultanous processing of the same page.

    with requests.get(locator.url, stream=True) as r:
        stuff = parse_link_header(locator.url, r.headers.get('Link', ''))
        scanner = PageScanner(locator.url)
        for chunk in r.iter_content(10_000, decode_unicode=True):
            scanner.feed(chunk)
        scanner.close()
        stuff += scanner.stuff

    update_locator_with_stuff(locator, stuff)
    locator.save()
    locator_post_scanned.send(Locator, locator=locator, stuff=stuff)
    return True


COMMA = re.compile(r'\s*,\s*')
SEMICOLON = re.compile(r'\s*;\s*')
EQUALS = re.compile(r'\s*=\s*')
LINK_HREF = re.compile(r'^<(.*)>$')
QUOTED = re.compile(r'^"(.*)"$')


def parse_link_header(base_url, comma_separated):
    """Given a base URL and a Link header value, return list of Link instancecs."""
    links = []
    for link_spec in COMMA.split(comma_separated.strip()):
        if not link_spec:
            continue
        href_part, *parts = SEMICOLON.split(link_spec)
        href = urljoin(base_url, LINK_HREF.sub(r'\1', href_part))
        for part in parts:
            prop, val = EQUALS.split(part, 1)
            if prop == 'rel':
                rel = QUOTED.sub(r'\1', val).split()
                break
        else:
            rel = None
        links.append(Link(rel, href))
    return links


def update_locator_with_stuff(locator, stuff):
    """Given stuff gathered about a page, update this locator.

    Does not save the locator.
    """
    titles = []  # List of candidate titles with weight. Pairs (WEIGHT, TITLE) where WEIGHT is a positive integer and TITLE is nonemoty.
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
                for img in thing.images:
                    thing, is_new = LocatorImage.objects.get_or_create(
                        locator=locator,
                        image=image_of_img(img))
        elif isinstance(thing, Img):
            LocatorImage.objects.get_or_create(locator=locator, image=image_of_img(thing))
    if titles:
        _, title = max(titles)
        if title:
            locator.title = title


def image_of_img(img):
    """Find or create the Image instance corresponding to this Img."""
    image, is_new = Image.objects.get_or_create(data_url=img.src, defaults={
        'media_type': img.type,
        'width': img.width,
        'height': img.height,
    })
    if not is_new and img.type or img.width or img.height:
        if img.type:
            image.media_type = img.type
        if img.width:
            image.width = img.width
        if img.height:
            image.height = img.height
        image.save()
    return image
