"""Signals that may be set."""

from django.conf import settings

from .tasks import retrieve_image_data,  sniff_image_data


def on_image_post_save(sender, instance, created, **kwargs):
    if created and not instance.retrieved and getattr(settings, 'IMAGES_FETCH_DATA', False):
        retrieve_image_data.delay(instance.pk, if_not_retrieved_since=None)
