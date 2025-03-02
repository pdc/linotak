"""MIddleware for the notes app."""

import re

from django.core.exceptions import MiddlewareNotUsed


class SubdomainSeriesMiddleware:
    """Middleware to add a series_name attribute to requests if they are on subdomains."""

    def __init__(self, get_response):
        from django.conf import settings

        if not hasattr(settings, "NOTES_DOMAIN"):
            raise MiddlewareNotUsed(
                "NOTES_DOMAIN not set so subdomain middleware not used"
            )
        domain = settings.NOTES_DOMAIN
        if not domain:
            raise MiddlewareNotUsed(
                "NOTES_DOMAIN empty so subdomain middleware not used"
            )

        self.subdomain_re = SubdomainSeriesMiddleware.regex_from_domain(domain)
        self.get_response = get_response

    def __call__(self, request):
        """Redirect to series URLconf if subdomain."""
        host = request.META.get("HTTP_HOST")
        if host:
            m = self.subdomain_re.match(host)
            if m:
                request.series_name = m.group(1)

        return self.get_response(request)

    @classmethod
    def regex_from_domain(cls, domain):
        return re.compile(r"^([a-z0-9-]{1,63})\." + re.escape(domain) + "$")
