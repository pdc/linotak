"""Handlers for signals."""

from celery import chain
from django.conf import settings

from .tasks import retrieve_image_data, sniff_image_data, create_image_square_representation


def on_image_post_save(sender, instance, created, **kwargs):
    if created and not instance.cached_data and not instance.retrieved and getattr(settings, 'IMAGES_FETCH_DATA', False):
        retrieve_image_data.delay(instance.pk, if_not_retrieved_since=None)


def on_image_wants_image_data(sender, instance, **kwargs):
    if instance.cached_data:
        sniff_image_data.delay(instance.pk)
    if not instance.cached_data and not instance.retrieved and getattr(settings, 'IMAGES_FETCH_DATA', False):
        retrieve_image_data.delay(instance.pk, if_not_retrieved_since=None)


def on_image_wants_square_representation(sender, instance, size, **kwargs):
    if instance.cached_data:
        create_image_square_representation.delay(instance.pk, size)
    elif getattr(settings, 'IMAGES_FETCH_DATA', False):
        chain(
            retrieve_image_data.s(instance.pk, if_not_retrieved_since=None),
            create_image_square_representation.si(instance.pk, size),
        ).delay()
