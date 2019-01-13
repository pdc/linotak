"""Handlers for signals."""

from celery import chain
from django.conf import settings

from .tasks import sniff_image_data


def on_image_post_save(sender, instance, created, **kwargs):
    if created and not instance.cached_data and not instance.retrieved and getattr(settings, 'IMAGES_FETCH_DATA', False):
        instance.queue_retrieve_data()


def on_image_wants_data(sender, instance, **kwargs):
    if instance.cached_data:
        sniff_image_data.delay(instance.pk)
    if not instance.cached_data and not instance.retrieved and getattr(settings, 'IMAGES_FETCH_DATA', False):
        instance.queue_retrieve_data()


def on_image_wants_square_representation(sender, instance, size, **kwargs):
    if instance.cached_data:
        instance.queue_square_representation(size)
    elif getattr(settings, 'IMAGES_FETCH_DATA', False):
        chain(
            instance.retrieve_data_task(),
            instance.square_representation_task(size),
        ).delay()
