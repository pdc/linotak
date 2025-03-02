"""Tasks that can be performed asynchronousely."""

from celery import shared_task
from celery.utils.log import get_task_logger

from .models import Outgoing, notify_webmention_receiver

logger = get_task_logger(__name__)


@shared_task(name="linotak.mentions.notify_outgoing_webmention_receiver")
def notify_outgoing_webmention_receiver(pk):
    mention = Outgoing.objects.get(pk=pk)
    notify_webmention_receiver(mention)
