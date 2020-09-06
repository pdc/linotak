"""Database models for app Linotak Mentions."""

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import requests

from ..notes.models import Locator, Note
from ..notes.scanner import Link, HEntry


class Receiver(models.Model):
    """A WebMention endpoint referenced, possibly indirectly, from a resource."""

    url = models.URLField(
        _('URL'),
        max_length=4000,
        unique=True,
    )

    created = models.DateTimeField(_('created'), default=timezone.now)

    class Meta:
        verbose_name = _('receiver')
        verbose_name_plural = _('receivers')

    def __str__(self):
        return self.url


class LocatorReceiver(models.Model):
    """Knowledge that this locator is associated with this WebMention receiver."""

    locator = models.OneToOneField(
        Locator,
        on_delete=models.CASCADE,
        related_name='mentions_info',
        verbose_name=_('locator'),
        help_text=_('Locator that is associated with receiver.'),
    )
    receiver = models.ForeignKey(
        Receiver,
        models.CASCADE,
        null=True,  # It is null if we have scaned locator and not found webmention link.
        blank=True,
        related_name='associated_locators',
        related_query_name='associated_locator',
        verbose_name=_('receiver'),
        help_text=_('Receiver handling mentions targeting the locator.'),
    )

    created = models.DateTimeField(_('created'), default=timezone.now)

    class Meta:
        verbose_name = _('locator receiver')
        verbose_name_plural = _('locator receivers')

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
        verbose_name=_('source'),
        help_text=_('Mentions an external resource.'),
    )
    target = models.ForeignKey(
        Locator,
        on_delete=models.CASCADE,
        related_name='outgoing_mentions',
        related_query_name='outgoing_mention',
        verbose_name=('target'),
        help_text=_('External resource mentioned in this note.'),
    )
    receiver = models.ForeignKey(  # Copied from locator when notifying in case it changes later.
        Receiver,
        on_delete=models.CASCADE,
        null=True,  # It is null if we havent scanned locaotr or if we did not find webmention link.
        blank=True,
        verbose_name=_('receiver'),
        help_text=_('Receiver used when notifying this locator.'),
    )

    discovered = models.DateTimeField(
        _('discovered'),
        blank=True,
        null=True,
        help_text=_('When the discovery phase of WebMention protocol concluded (successfully or otherwise).'),
    )
    notified = models.DateTimeField(
        _('notified'),
        blank=True,
        null=True,
        help_text=_('When the notification of the receiver concluded (successfully or otherwise)'),
    )
    response_status = models.PositiveIntegerField(
        _('response status'),
        null=True,
        blank=True,
        help_text=_('HTTP status code returned by receiver when notified.'),
    )

    created = models.DateTimeField(_('created'), default=timezone.now)

    class Meta:
        verbose_name = 'outgoing mention'
        verbose_name_plural = 'outgoing mentions'

    def make_discovered(self, now, receiver):
        """Discovery has discovered the Webmention endpoint relevant to this mention.

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

    MENTION, LIKE, REPOST, REPLY = range(4)
    INTENTS = MENTION, LIKE, REPOST, REPLY
    INTENT_LABELS = _('Mention'), _('Like'), _('Repost'), _('Reply')
    INTENT_CHOICES = zip(INTENTS, INTENT_LABELS)

    source = models.ForeignKey(
        Locator,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('source'),
        help_text=_('Location of a post that mentions one of our notes, if known.'),
    )
    target = models.ForeignKey(
        Note,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('target'),
        help_text=_('The note that is mentioned by the source, if known.'),
    )

    source_url = models.URLField(
        _('source URL'),
        max_length=4000,
        help_text=_('URL of a page mentioning oine of our notes, as supplied by caller.'),
    )
    target_url = models.URLField(
        _('targeet URL'),
        max_length=4000,
        help_text=_('URL of one of our notes, as supplied by caller.'),
    )
    user_agent = models.CharField(
        _('user agent'),
        max_length=4000,
        null=True,
        blank=True,
        help_text=_('What software the caller claims to be running.'),
    )
    intent = models.PositiveSmallIntegerField(
        _('intent'),
        null=True,
        blank=True,
        choices=INTENT_CHOICES,
        help_text=_('Inferred intent of the mention.')
    )

    created = models.DateTimeField(_('created'), default=timezone.now)
    received = models.DateTimeField(_('received'), default=timezone.now)
    scanned = models.DateTimeField(_('scanned'), null=True, blank=True, help_text='When source erntry was scanned')
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

    class Meta:
        verbose_name = _('incoming mention')
        verbose_name_plural = _('incoming mentions')

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


CLASS_INTENTS = {
    'u-like-of': Incoming.LIKE,
    'u-repost-of': Incoming.REPOST,
}


def handle_locator_post_scanned(sender, locator, stuff, **kwargs):
    """Called after a locator has been scanned. Look for webmention links."""
    # Find if ther is an endpoint for outgoing Webmention notifications.
    for link in entry_links(stuff):
        if 'webmention' in link.rel:
            receiver, is_new = Receiver.objects.get_or_create(url=link.href)
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

    # Is this the source of an incoming Webmention?
    for incoming in locator.incoming_set.all():
        for link in entry_links(stuff):
            if link.href == incoming.target_url:
                for css_class in link.classes:
                    if (intent := CLASS_INTENTS.get(css_class)):
                        break
                else:
                    intent = Incoming.MENTION
                incoming.intent = intent
                incoming.scanned = timezone.now()
                incoming.save()
                break


def entry_links(stuff):
    """Given stuff gleaned from a locator, return links that might we webmention links."""
    for thing in stuff:
        if isinstance(thing, Link):
            yield thing
        if isinstance(thing, HEntry):
            yield from thing.links


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
