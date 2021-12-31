"""Celery tasks for images app."""

from celery import shared_task
from celery.utils.log import get_task_logger
from django.db import transaction

from ..utils import datetime_of_timestamp
from .models import Image
from .size_spec import SizeSpec


logger = get_task_logger(__name__)


@shared_task(name="linotak.images.retrieve_image_data")
def retrieve_image_data(pk, if_not_retrieved_since):
    """Task to request image content via HTTP and hence determine format and dimensions.

    Arguments --
        pk -- (integer) identifies the image within the database
        if_not_retrieved_since -- (seconds since epoch) cutoff for retrieving the imaage, or None

    If if_not_retrieved_since is specified then the retrieval
    is suppressed if the image has been retrieved after
    the specified date and time.
    """
    image = Image.objects.get(pk=pk)
    image.retrieve_data(
        if_not_retrieved_since=datetime_of_timestamp(if_not_retrieved_since), save=True
    )
    image.delete_if_small()


@shared_task(name="linotak.images.sniff_image_data")
def sniff_image_data(pk):
    """Task to request image content be scanned for format and dimensions.

    Argument --
        pk -- (integer) identifies the image within the database
    """
    with transaction.atomic():
        try:
            image = Image.objects.get(pk=pk)
            image.sniff(save=True)
            image.delete_if_small()
        except Image.NotSniffable as e:
            logger.warning(e)


@shared_task(name="linotak.images.create_image_representation")
def create_image_representation(pk, spec):
    """Task to generate a square representation of an image.

    Argument --
        pk -- (integer) identifies the image within the database
        spec -- (SizeSpec intance) specifies the width and height in pixels
    """
    Image.objects.get(pk=pk).create_representation(SizeSpec.parse(spec))
