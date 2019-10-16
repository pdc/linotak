"""Database models for app Linotak Mentions."""

from django.db import models, transaction
from django.utils import timezone
import requests

from ..notes.models import Locator, Note
from ..notes.scanner import Link


class Receiver(models.Model):
    """A WebMention endpoint referenced perhaps indirectly from a resource."""

    url = models.URLField(
        max_length=4000,
        unique=True,
    )

    created = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.url


class Outgoing(models.Model):
    """A mention of an external resource from one of our notes.

    Basic plan is as follows:
    - Note is created and it mentions a resource
    - Outgoing instance is created with note and targe
    - When locator is scanned, Receiver field is of outgoing mention is filled in and queued for notification
    - Asyncronous task sends notification and fills in `done` field

    """

    source = models.ForeignKey(
        Note,
        on_delete=models.CASCADE,
        related_name='outgoing_mentions',
        related_query_name='outgoing_mention',
        help_text='Mentions an external resource.',
    )
    target = models.ForeignKey(
        Locator,
        on_delete=models.CASCADE,
        related_name='outgoing_mentions',
        related_query_name='outgoing_mention',
        help_text='External resource mentioned in this note.',
    )
    receiver = models.ForeignKey(
        Receiver,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='outgoing_mentions',
        related_query_name='outgoing_mention',
        help_text='Receiver handling mentions for the target, if known.',
    )

    discovered = models.DateTimeField(
        blank=True,
        null=True,
        help_text='When the discovery phase of WebMention protocol concluded (successfully or otherwise).',
    )
    notified = models.DateTimeField(
        blank=True,
        null=True,
        help_text='When the notification of the receiver concluded (successfully or otherwise)',
    )
    response_status = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='HTTP status code returned by receiver when notified.'
    )

    created = models.DateTimeField(default=timezone.now)


def handle_locator_scanned(sender, locator, stuff, **kwargs):
    """Handler for post_locator_scanned signal."""
    for thing in stuff:
        if isinstance(thing, Link) and 'webmention' in thing.rel:
            receiver, is_new = Receiver.objects.get_or_create(url=thing.href)
            break
    else:
        receiver = None
    Outgoing.objects.filter(target=locator, discovered__isnull=True).update(receiver=receiver, discovered=timezone.now())


def notify_outgoing_mention(mention):
    """Called from task to make HTTP requests to this mention of a locator."""
    if mention.notified:
        # Already done so no action required.
        return
    with transaction.atomic():
        if not mention.notified:
            # Mark as done prematurely to prevent accidental concurrent notifications.
            mention.notified = timezone.now()
            mention.save()
            r = requests.get(mention.receiver.url, {
                'source': mention.source.get_absolute_url(with_host=True),
                'target': mention.target.url
            })
            mention.response_status = r.status_code
            mention.save()

