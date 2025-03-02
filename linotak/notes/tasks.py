"""Celery tasks for notes app."""

from celery import shared_task
from celery.utils.log import get_task_logger

from ..utils import datetime_of_timestamp
from .models import Locator
from .updating import fetch_page_update_locator

logger = get_task_logger(__name__)


@shared_task(name="linotak.notes.fetch_locator_page")
def fetch_locator_page(pk, if_not_scanned_since):
    locator = Locator.objects.get(pk=pk)
    fetch_page_update_locator(
        locator, if_not_scanned_since=datetime_of_timestamp(if_not_scanned_since)
    )
