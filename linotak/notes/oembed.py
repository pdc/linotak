"""Instead of scanning page, scan read its oEmbed profile."""

from dataclasses import dataclass
import logging
import re
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
import requests
from uritemplate import URITemplate

from .scanner import HCard, Img, Title


LOG = logging.getLogger(__name__)


@dataclass
class OEmbedEndpoint:
    """One mapping from provider resource patterns to url template for oEmbed.

    Generally tese are created using the `from_json` classmethod.

    If any of the patterns match the resource URL, then the url_template
    property says how to get the oembed resource.
    """

    pattern: re.Pattern  # Used to see if URL matches.
    template: URITemplate  # Used to locate the oEmbed resource

    def url_for(self, resource_url):
        if self.pattern.match(resource_url):
            return self.template.expand(url=resource_url, format="json")

    @classmethod
    def from_json(cls, obj: dict) -> "OEmbedEndpoint":
        """Create from the format found in the providers list at https://oembed.com/providers.json.

        Arguments --
            url_globs -- One or more URL patterns, using * as a wildcard. Not entirely unlike glob.
            oembed_url --  Template for the oEmbedesource.
                The data provided omits the {?…} part with the standard parameters.
                But it may include `{formt}` in the path.
        """
        if url_globs := obj.get("schemes"):
            return cls(re_from_url_globs(url_globs), template_from_oembed(obj["url"]))
        LOG.info("oEmbed provider: no resource URLs for %s", obj["url"])


def get_endpoints() -> list[OEmbedEndpoint]:
    """Lazily load the providers file using the OEMBED_PROVIDERS_URL setting."""
    if not settings.OEMBED_PROVIDERS_URL:
        return []
    cache_key = settings.OEMBED_PROVIDERS_URL
    if answer := cache.get(cache_key):
        return answer
    answer = load_endpoints()
    cache.set(cache_key, answer, settings.OEMBED_PROVIDERS_TTL)
    return answer


def load_endpoints() -> list[OEmbedEndpoint]:
    """Load the providers using the OEMBED_PROVIDERS_URL setting."""
    r = requests.get(settings.OEMBED_PROVIDERS_URL)
    if r.ok:
        specs = r.json()
        result = [
            OEmbedEndpoint.from_json(endpoint_spec)
            for spec in specs
            for endpoint_spec in spec["endpoints"]
            if endpoint_spec.get("schemes")
        ]
        LOG.info(
            "Loaded %d endpoints from %s", len(result), settings.OEMBED_PROVIDERS_URL
        )
        return result
    LOG.warning("Failed to load %s: %d", settings.OEMBED_PROVIDERS_URL, r.status_code)
    return []


def fetch_oembed(url: str) -> list | None:
    """Return results of fetching oEmbed resource for this URL, or None.

    <https://oembed.com#section2.1>

    """
    for endpoint in get_endpoints():
        if oembed_url := endpoint.url_for(url):
            LOG.info("Fetching oEmbed %s", oembed_url)
            r = requests.get(
                oembed_url,
                headers={
                    "accept": "application/json",
                    "User-Agent": settings.NOTES_FETCH_AGENT,
                },
            )
            if r.ok:
                return stuffs_from_oembed(r.json())
            LOG.warning(f"Fetching oEmbed failed: {r.status_code} getting {oembed_url}")


def re_from_url_globs(url_globs: list[str]) -> re.Pattern:
    """Given a list of patterns like oEmbed configuration, return regexp matching URLs.

    <https://oembed.com#section2.1>
    """
    res = []
    for url_glob in url_globs:
        u = urlparse(url_glob)
        path_re = ".*".join(re.escape(frag) for frag in u.path.split("*"))
        if u.netloc.startswith("*."):
            netloc_re = r"(?:[a-z0-9.-]+)?" + re.escape(u.netloc[2:])
        else:
            netloc_re = re.escape(u.netloc)
        res.append(u.scheme + "://" + netloc_re + path_re)
    return re.compile("|".join(res))


def template_from_oembed(oembed_url: str) -> URITemplate:
    if "{format}" in oembed_url:
        return URITemplate(oembed_url + "{?url,maxwidth,maxheight}")
    return URITemplate(oembed_url + "{?url,maxwidth,maxheight,format}")


def stuffs_from_oembed(obj: dict) -> list:
    result = []
    if obj.get("type") == "photo" and (src := obj.get("url")):
        result.append(
            Img(
                src, width=obj.get("width"), height=obj.get("height"), classes=["photo"]
            )
        )
    if src := obj.get("thumbnail_url"):
        result.append(
            Img(
                src,
                width=obj.get("thumbnail_width"),
                height=obj.get("thumbnail_height"),
                classes=["thumbnail"],
            )
        )
    if title := obj.get("title"):
        result.append(Title(title))
    if author_name := obj.get("author_name"):
        result.append(HCard(author_name, obj.get("author_url")))
    return result
