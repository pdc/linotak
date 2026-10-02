"""Routines for fetching HTTP respources with just a little hint of caution."""

import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

import requests
import validators
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from requests import Response


def validate_schema(scheme: str) -> bool:
    return scheme in {"http", "https"}


def clean_url(url: str) -> str | None:
    """Check this URL is one we are willing to fetch and return cleaned version.

    Want to avoid
    - bogus URLs
    - non-HTTP URLs
    - URLs that reference internal serivces (should they exist)

    This may entail doing a DNS lookup for the URL.

    Returns a tidied version of the URL.
    """
    if not validators.url(
        url,
        private=False,
        skip_ipv4_addr=True,
        skip_ipv6_addr=True,
        strict_query=True,
        consider_tld=True,
        validate_scheme=validate_schema,
    ):
        raise ValidationError(_("Not a valid URL"), "bad_url")
    split = urlsplit(url)

    # Want to ensure no address this hostname maps to is private.
    for record in socket.getaddrinfo(
        split.hostname, split.port, proto=socket.IPPROTO_TCP, flags=socket.AI_ALL
    ):
        addr_spec = record[-1]
        addr = ipaddress.ip_address(addr_spec[0])
        if not addr.is_global:
            raise ValidationError(_("Hostname is not global"), code="url_not_global")

    return urlunsplit(split)


def fetch(url: str, *args, max_redirects=15, headers={}, **kwargs) -> Response | None:
    """Do a GET request on this URL, if it is fetchable."""
    # Always a GET request & always without any cookies or special authentication.
    r = requests.get(
        clean_url(url),
        allow_redirects=False,
        headers=headers | {"User-Agent": settings.NOTES_FETCH_AGENT},
        **kwargs,
    )
    if r.status_code in (301, 302, 307, 308):
        # Redirect.
        # Because we are doing plain GET of public URLs we do not need to faff
        # with copying cookies or payloads about. But we do want to clean the
        # resulting URL.
        next_url = r.headers["location"]
        if max_redirects > 0:
            return fetch(next_url, *args, max_redirects=max_redirects - 1, **kwargs)
        raise ValidationError(_("Too many redirects"), "url_too_many_redirects")
    return r
