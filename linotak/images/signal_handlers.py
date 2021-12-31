"""Handlers for signals."""

from celery import chain
from django.conf import settings

from .tasks import sniff_image_data


def on_image_post_save(sender, instance, created, **kwargs):
    if (
        created
        and not instance.cached_data
        and not instance.retrieved
        and (not instance.width or instance.width >= 40)
        and getattr(settings, "IMAGES_FETCH_DATA", False)
    ):
        instance.queue_retrieve_data()


def on_image_wants_data(sender, instance, **kwargs):
    if instance.cached_data:
        sniff_image_data.delay(instance.pk)
    if (
        not instance.cached_data
        and not instance.retrieved
        and getattr(settings, "IMAGES_FETCH_DATA", False)
    ):
        instance.queue_retrieve_data()


def on_image_wants_representation(sender, instance, spec, **kwargs):
    if instance.cached_data:
        instance.queue_representation(spec)
    elif getattr(settings, "IMAGES_FETCH_DATA", False):
        chain(
            instance.retrieve_data_task(),
            instance.representation_task(spec),
        ).delay()


def on_image_pre_delete(sender, instance, **kwargs):
    """Tidy away image file."""
    if instance.cached_data:
        instance.cached_data.delete(save=False)


def on_representation_pre_delete(sender, instance, **kwargs):
    """Tidy away image file."""
    if instance.content:
        instance.content.delete(save=False)
