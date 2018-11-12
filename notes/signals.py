"""Signals that may be set."""

from django.conf import settings

from .tasks import fetch_locator_page


def on_locator_post_save(sender, instance, created, **kwargs):
    if created and settings.NOTES_FETCH_LOCATORS:
        fetch_locator_page.delay(instance.pk)
