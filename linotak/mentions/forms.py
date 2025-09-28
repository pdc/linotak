"""Forms for WebMenion support."""

from urllib.parse import urlparse

from django import forms
from django.conf import settings
from django.urls import Resolver404, resolve
from django.utils import timezone

from ..notes.middleware import SubdomainSeriesMiddleware
from ..notes.models import Locator, Note
from .models import Incoming


class IncomingForm(forms.Form):
    """Receiver for WebMention requests.

    Called bu outside web sites to notify us they have linked to a note.
    """

    source = forms.URLField(
        max_length=4000,
        assume_scheme="https",
    )
    target = forms.URLField(
        max_length=4000,
        assume_scheme="https",
    )

    def save(self, http_user_agent):
        """Create and return an Incoming instance.

        Arguments:
            `http_user_agent`: the `User-Agent` header from the request.

        Returns:
            Newly created `Incoming` instance.
        """
        source_url = self.cleaned_data["source"]
        target_url = self.cleaned_data["target"]

        target = None
        parsed = urlparse(target_url)
        # Check the host & port part of the target URL is  one of ours.
        m = SubdomainSeriesMiddleware.regex_from_domain(settings.NOTES_DOMAIN).match(
            parsed.netloc
        )
        if m:
            series_name = m.group(1)
            try:
                match = resolve(parsed.path)
                if match.url_name == "detail":
                    pk = match.kwargs.get("pk")
                    if pk:
                        target = Note.objects.get(pk=pk, series__name=series_name)
            except Resolver404:
                pass
            except Note.DoesNotExist:
                pass

        if target:
            source, source_is_new = Locator.objects.get_or_create(url=source_url)
        else:
            # No point scanning source if we cannot associate it with a note.
            source = None

        result, is_new = Incoming.objects.update_or_create(
            source_url=source_url,
            target_url=target_url,
            defaults={
                "user_agent": http_user_agent,
                "source": source,
                "target": target,
                "received": timezone.now(),
            },
        )
        return result
