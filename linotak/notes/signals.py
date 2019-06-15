"""Signals that may be set."""

from django.conf import settings


def on_locator_post_save(sender, instance, created, **kwargs):
    if created and settings.NOTES_FETCH_LOCATORS:
        instance.queue_fetch()
