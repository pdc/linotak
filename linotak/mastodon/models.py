from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import logging
import requests
import requests_oauthlib
import time

from ..images.size_spec import SizeSpec
from ..notes.models import Series, Note

from .protocol import authorize_path, token_path, verify_credentials_path, media_path, statuses_path, necessary_scopes


logger = logging.getLogger(__name__)

# My first thought was to have Server & Connection classes, where the former
# represetns on Mastodon instance we have regstered the app at.
# But Mastodon has a registration API that makes this redundant so
# the two classes are collapsed together as Connection


class ConnectionManager(models.Manager):

    def create_connection(self, series, domain):
        """Create a connection instance to authenticate with this domain.

        Arguments --
            series -- Series instance that will be connected to an account on this domain.
            domain -- names a Masotodon instance to connect to (is a host name like `mastodon.social`).

        Returns --
            a Connection isntance that has blank access token
            (and so needs to gop through the OAuth2 dance to be of any use).
        """
        r = requests.post(
            f'https://{domain}/api/v1/apps',
            data={
                'client_name': series.domain,
                'redirect_uris': series.make_absolute_url(reverse('mastodon:callback')),
                'scopes': ' '.join(necessary_scopes),
                'website': series.make_absolute_url('/'),
            },
            headers={
                'Accept': 'application/json',
            }
        )
        response_body = r.json()
        if r.status_code in (200, 201):
            return self.create(
                series=series,
                domain=domain,
                client_id=response_body['client_id'],
                client_secret=response_body['client_secret'],
            )
        logger.error(f"Could not enroll with {domain}: {response_body.get('error', response_body)}")


class Connection(models.Model):
    """Link between a Linotak series and a Mastodon account."""

    series = models.ForeignKey(
        Series,
        models.CASCADE,
        related_name='mastodon_connections',
        related_query_name='mastodon_connection',
        verbose_name=_('series'),
    )

    domain = models.CharField(
        _('domain'),
        max_length=255,
        help_text=_('Domain name of the Mastodon instance.'),
    )
    name = models.CharField(
        _('name'),
        max_length=255,  # Could not find definitive limit on the size of a username on Mastodon.
        help_text=_('Name of user on that instance (without the @ signs and without the domain name)')
    )
    client_id = models.CharField(
        _('client ID'),
        max_length=255,
        help_text=_('OAuth2 credential supplied by Mastodon instance when enrolling the app.'),
    )
    client_secret = models.CharField(
        _('client secret'),
        max_length=255,
        help_text=_('OAuth2 credential supplied by Mastodon instance when enrolling the app.'),
    )
    access_token = models.TextField(
        _('access token'),
        null=True,
        blank=True,
    )
    refresh_token = models.TextField(
        _('refresh token'),
        null=True,
        blank=True,
    )
    expires_at = models.BigIntegerField(
        _('expires at'),
        null=True, blank=True,
        help_text=_('When the access token expires, in seconds since 1970-01-01, or null'),
    )
    created = models.DateTimeField(_('created'), default=timezone.now)
    modified = models.DateTimeField(_('modified'), auto_now=True)

    objects = ConnectionManager()

    class Meta:
        unique_together = (('series', 'domain', 'name'),)
        verbose_name = _('connection')
        verbose_name_plural = _('connections')

    def __str__(self):
        """Return Mastodon username in full form."""
        return f'@{self.name}@{self.domain}'

    @property
    def authorize_url(self):
        return f'https://{self.domain}{authorize_path}'

    @property
    def token_url(self):
        return f'https://{self.domain}{token_path}'

    @property
    def verify_credentials_url(self):
        return f'https://{self.domain}{verify_credentials_path}'

    @property
    def media_url(self):
        return f'https://{self.domain}{media_path}'

    @property
    def statuses_url(self):
        return f'https://{self.domain}{statuses_path}'

    def make_oauth(self):
        """Return an OAuth2 porocessor.

        If not authenticated, create an OAuth2 client ready for authentication.
        If authenticated, return one authenticated with token.
        """
        if self.access_token:
            return requests_oauthlib.OAuth2Session(
                self.client_id,
                token=self.retrieve_token(),
            )

        # Forced to return an aunauthenticated token.
        redirect_uri = self.series.make_absolute_url(reverse('mastodon:callback'))
        return requests_oauthlib.OAuth2Session(
            self.client_id,
            redirect_uri=redirect_uri,
            scope=necessary_scopes,
        )

    def save_token(self, token, save=True):
        self.access_token = token['access_token']
        self.refresh_token = token.get('refresh_token')
        self.expires_at = int(time.time() + float(token['expires_in'])) if 'expires_in' in token else None
        if save:
            self.save()

    def retrieve_token(self):
        return {
            'access_token': self.access_token,
            'token_type': 'Bearer',
        }


class Post(models.Model):
    """Link to an toot (post on mastodon) from one of our notes.

    Mastodon API calls this a status.
    """

    max_media = 4
    media_size_spec = SizeSpec(1280, 1280)  # Mastodon docs say images are limited to 1.6 MPixel

    connection = models.ForeignKey(
        Connection,
        models.SET_NULL,
        null=True,  # Null means the connection was destroyed after post created.
        verbose_name=_('connection'),
        help_text=_('Mastodon instance where this note was created'),
    )
    note = models.ForeignKey(
        Note,
        models.SET_NULL,  # Even if we destroy the record of why we created the post the post still exists.
        null=True,  # Null means the note was destroyed after post created.
        related_name='mastodon_posts',
        related_query_name='mastodon_post',
        verbose_name=_('note'),
    )

    their_id = models.CharField(
        _('their ID'),
        max_length=255,
        help_text=_('Identifies the post in the scope of the instance'),
    )
    url = models.URLField(
        _('URL'),
        max_length=1024,
        help_text=_('Canonical web page of the post')
    )
    posted = models.DateTimeField(_('posted'), null=True, blank=True)
    created = models.DateTimeField(_('created'), default=timezone.now)
    modified = models.DateTimeField(_('modified'), auto_now=True)

    class Meta:
        unique_together = (('connection', 'note'),)
        ordering = ('-created',)
        verbose_name = _('post')
        verbose_name_plural = _('posts')

    def __str__(self):
        return f'{self.note} ({self.connection})'

    def post_to_mastodon(self):
        """Issue request to Mastodion instance to create a status."""

        if self.posted:
            logger.warn(f'Tried to repost {self.pk} ({self.note}) to {self.connection}')
            return

        # Before starting transaction do stuff that can be harmlessly repeated,
        # like generating representations of images.

        oauth = self.connection.make_oauth()
        data = {
            'status': self.note.text_with_links(max_length=500, url_length=23),
        }

        for locator in self.note.subjects.all():
            if (image := locator.main_image()):
                if len(data.setdefault('media_ids', [])) < self.max_media:
                    representation = image.create_representation(self.media_size_spec)
                    files = {'file': (representation.content.name, representation.content.open(), representation.media_type)}
                    if image.focus_x == 0.5 and image.focus_y == 0.5:
                        r = oauth.post(self.connection.media_url, files=files)
                    else:
                        r = oauth.post(
                            self.connection.media_url,
                            files=files,
                            data={'focus': f'{2.0 * image.focus_x - 1.0},{-2.0 * image.focus_y + 1.0}'},
                        )
                    r.raise_for_status()
                    media = r.json()
                    data['media_ids'].append(media['id'])
                    if locator.sensitive:
                        data['sensitive'] = True

        with transaction.atomic():
            if self.posted:
                logger.warn(f'Tried to repost {self.pk} ({self.note}) to {self.connection}')
                return
            self.posted = timezone.now()
            self.save()

            r = oauth.post(
                self.connection.statuses_url,
                json=data,
                headers={
                    'Accept': 'application/json',
                    'Idempotency-Key': self.note.get_absolute_url(with_host=True),
                },
            )
            r.raise_for_status()
            status = r.json()

            self.their_id = status.get('id')
            self.url = status.get('url')
            self.save()
