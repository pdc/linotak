"""Celery tasks for images app."""

from celery import shared_task
from celery.utils.log import get_task_logger
from django.db import transaction

from .models import Image


logger = get_task_logger(__name__)


@shared_task(name='tanolin.images.retrieve_image_data')
def retrieve_image_data(pk, if_not_retrieved_since):
    with transaction.atomic():
        Image.objects.get(pk=pk).retrieve_data(if_not_retrieved_since=if_not_retrieved_since, save=True)


@shared_task(name='tanolin.images.sniff_image_data')
def sniff_image_data(pk):
    with transaction.atomic():
        try:
            Image.objects.get(pk=pk).sniff(save=True)
        except Image.NotSniffable as e:
            logger.warning(e)


@shared_task(name='tanolin.images.create_image_square_representation')
def create_image_square_representation(pk, size):
    Image.objects.get(pk=pk).create_square_representation(size)
