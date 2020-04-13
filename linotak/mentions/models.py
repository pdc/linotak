"""Database models for app Linotak Mentions."""

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction
from django.urls import reverse
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


class LocatorReceiver(models.Model):
    """Knowledge that this locator is associated with this WebMention receiver."""

    locator = models.OneToOneField(
        Locator,
        on_delete=models.CASCADE,
        related_name='mentions_info',
        help_text='Locator that is associated with receiver.',
    )
    receiver = models.ForeignKey(
        Receiver,
        on_delete=models.CASCADE,
        null=True,  # It is null if we have scaned locator and not found webmention link.
        blank=True,
        related_name='associated_locators',
        related_query_name='associated_locator',
        help_text='Receiver handling mentions targeting the locator.',
    )

    created = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return str(self.locator)


class Outgoing(models.Model):
    """A mention of an external resource from one of our notes.

    Basic plan is as follows:
    - Note is created and it mentions a resource
    - Outgoing instance is created with note and target
    - When locator is scanned, Receiver field of outgoing mention is filled in and queued for notification
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
    receiver = models.ForeignKey(  # Copied from locator when notifying in case it changes later.
        Receiver,
        on_delete=models.CASCADE,
        null=True,  # It is null if we havent scanned locaotr or if we did not find webmention link.
        blank=True,
        help_text='Receiver used when notifying this locator.',
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

    def make_discovered(self, now, receiver):
        """Discovery has discovered the Webmention ednpoint relevant to this mention.

        Arguments --
            now -- when discovery occurred
            receiver -- a Receiver instance

        May trigger notification if `MENTIONS_POST_NOTIFICATIONS` is true.
        """
        self.receiver = receiver
        self.discovered = now
        self.save()

        if receiver and settings.MENTIONS_POST_NOTIFICATIONS:
            self.notify_receiver()

    def notify_receiver(self):
        """Queue the HTTP request to the Webmention endpoint."""
        from .tasks import notify_outgoing_webmention_receiver

        transaction.on_commit(lambda: notify_outgoing_webmention_receiver.delay(self.pk))


class Incoming(models.Model):
    """Record of a POST request to our webmention receiver.

    Basic plan is:
    - find a matching Note instance
    - queue a scan of the target URL
    - in handler for scanning, determine whether target has URL of source in it
    - (moderation step might happen here)

    """

    source = models.ForeignKey(
        Locator,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Location of a post that mentions one of our notes, if known.'
    )
    target = models.ForeignKey(
        Note,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='The note that is mentioned by the source, if known.'
    )

    source_url = models.URLField(
        max_length=4000,
        help_text='URL of a page mentioning oine of our notes, as supplied by caller.'
    )
    target_url = models.URLField(
        max_length=4000,
        help_text='URL of one of our notes, as supplied by caller.'
    )
    user_agent = models.CharField(
        max_length=4000,
        null=True,
        blank=True,
        help_text='What software the caller claims to be running.'
    )

    created = models.DateTimeField(default=timezone.now)
    # target_acquired = models.DateTimeField(
    #     blank=True,
    #     null=True,
    #     help_text='When the the target note was identified.',
    # )
    # source_queued = models.DateTimeField(
    #     blank=True,
    #     null=True,
    #     help_text='When the the source Locator instance was created and queued for scanning.',
    # )
    # source_checked = models.DateTimeField(
    #     blank=True,
    #     null=True,
    #     help_text='When the the source was checked for having a valid mention of the target (whether passed or failed).',
    # )

    def __str__(self):
        return self.source_url

    def get_absolute_url(self):
        return reverse('incoming-detail', kwargs={'pk': self.pk})


def handle_note_post_save(sender, instance, created, raw, **kwargs):
    """Handler for post_save of note.

    If it is published then create mentions for subjects.
    """
    if not raw and instance.published:
        for locator in instance.subjects.all():
            outgoing = Outgoing.objects.create(source=instance, target=locator)
            if hasattr(locator, 'mentions_info'):  # Discovery has already happened.
                outgoing.make_discovered(locator.mentions_info.created, locator.mentions_info.receiver)


def handle_locator_post_scanned(sender, locator, stuff, **kwargs):
    """Handler for locator_post_scanned signal."""
    for thing in stuff:
        if isinstance(thing, Link) and 'webmention' in thing.rel:
            receiver, is_new = Receiver.objects.get_or_create(url=thing.href)
            break
    else:
        receiver = None

    try:
        location_receiver = locator.mentions_info
        if location_receiver.receiver != receiver:
            location_receiver.receiver = receiver
            location_receiver.save()
    except ObjectDoesNotExist:
        LocatorReceiver.objects.create(locator=locator, receiver=receiver)

    now = timezone.now()
    for mention in Outgoing.objects.filter(target=locator, discovered__isnull=True):
        mention.make_discovered(now, receiver)


def notify_webmention_receiver(mention):
    """Called from task to make HTTP requests to this mention of a locator."""
    if mention.notified:
        # Already done so no action required.
        return

    with transaction.atomic():
        if not mention.notified:
            # Mark as done prematurely to prevent accidental concurrent notifications.
            mention.notified = timezone.now()
            mention.save()
            r = requests.post(mention.target.mentions_info.receiver.url, data={
                'source': mention.source.get_absolute_url(with_host=True),
                'target': mention.target.url
            })
            mention.response_status = r.status_code
            mention.save()
