"""ROutines for updating information about external resources."""

import requests

from .models import Locator
from .scanner import PageScanner, Title, HCard, HEntry


def fetch_page_update_locator(locator):
    """Download and scan the web page thus locator references and update it."""
    with requests.get(locator.url, stream=True) as r:
        scanner = PageScanner(locator.url)
        for chunk in r.iter_content(10_000, decode_unicode=True):
            scanner.feed(chunk)
        scanner.close()
        stuff = scanner.stuff

    update_locator_with_stuff(locator, stuff)


def update_locator_with_stuff(locator, stuff):
    """Given stuff gathered about a page, update our stored information."""
    titles = []
    for thing in stuff:
        if isinstance(thing, Title):
            titles.append((1, thing.text))
        elif isinstance(thing, HEntry):
            titles.append((2, thing.name))
            if thing.summary:
                locator.text = thing.summary
    _, title = max((s, v) for s, v in titles if v)
    if title:
        locator.title = title
    locator.save()


