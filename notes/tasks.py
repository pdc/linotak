"""Celery tasks for notes app."""

from celery import shared_task
from celery.utils.log import get_task_logger

from .models import Locator
from .updating import fetch_page_update_locator


logger = get_task_logger(__name__)


@shared_task
def fetch_locator_page(pk):
    locator = Locator.objects.get(pk=pk)
    fetch_page_update_locator(locator)
    # logger.info('Updated locator %s', locator)


@shared_task
def mul(x, y):
    return x * y


@shared_task
def xsum(numbers):
    return sum(numbers)
