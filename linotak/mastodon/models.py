from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import requests_oauthlib
import time

from ..notes.models import Series, Note

from .protocol import authorize_path, token_path, verify_credentials_path, statuses_path, necessary_scopes


class Server(models.Model):
    """A Mastodon instance we gave registered an app token with.

        Using the term ‘server’ because ‘instance’ has special meaning in Django.
    """

    name = models.CharField(
        max_length=255,
        verbose_name=_('domain name'),
        help_text=_('Domain name of the Mastodon instance.'),
    )
    client_id = models.CharField(
        max_length=255,
        verbose_name=_('client ID'),
        help_text=_('Supplied by Mastodon instance when entrolling the app.'),
    )
    client_secret = models.CharField(
        max_length=255,
        verbose_name=_('client secret'),
        help_text=_('Supplied by Mastodon instance when entrolling the app.'),
    )

    created = models.DateTimeField(_('created'), default=timezone.now)
    modified = models.DateTimeField(_('modified'), auto_now=True)

    class Meta:
        verbose_name = _('server')
        verbose_name_plural = _('servers')

    def __str__(self):
        return self.name

    @property
    def authorize_url(self):
        return f'https://{self.name}{authorize_path}'

    @property
    def token_url(self):
        return f'https://{self.name}{token_path}'

    @property
    def verify_credentials_url(self):
        return f'https://{self.name}{verify_credentials_path}'

    @property
    def statuses_url(self):
        return f'https://{self.name}{statuses_path}'


class Connection(models.Model):
    """Link between a Linotak series and a Mastodon account."""

    series = models.ForeignKey(
        Series,
        models.CASCADE,
        verbose_name=_('series'),
    )
    server = models.ForeignKey(
        Server,
        models.CASCADE,
        verbose_name=_('server'),
    )

    name = models.CharField(
        max_length=255,  # Could not find definitive limit on the size of a username on Mastodon.
        verbose_name=_('name'),
        help_text=_('Name of user on that instance (without the @ signs and without the domain name)')
    )
    access_token = models.TextField(null=True, blank=True)
    refresh_token = models.TextField(null=True, blank=True)
    expires_at = models.BigIntegerField(
        null=True, blank=True,
        help_text='When the access token expires, in seconds since 1970-01-01',
    )
    created = models.DateTimeField(_('created'), default=timezone.now)
    modified = models.DateTimeField(_('modified'), auto_now=True)

    class Meta:
        unique_together = (('series', 'server', 'name'),)
        verbose_name = _('connection')
        verbose_name_plural = _('connections')

    def __str__(self):
        """Return Mastodon username in full form."""
        return f'@{self.name}@{self.server.name}'

    def make_oauth(self):
        """Return an OAuth2 porocessor.

        If not authenticated, create an OAuth2 client ready for authentication.
        If authenticated, return one authenticated with token.
        """
        if self.access_token:
            return requests_oauthlib.OAuth2Session(
                self.server.client_id,
                token=self.access_token,
            )

        # Forced to return an aunauthenticated token.
        redirect_uri = self.series.make_absolute_url(reverse('mastodon:callback'))
        return requests_oauthlib.OAuth2Session(
            self.server.client_id,
            redirect_uri=redirect_uri,
            scope=necessary_scopes,
        )

    def save_token(self, token, save=True):
        self.access_token = token['access_token']
        self.refresh_token = token.get('refresh_token')
        self.expires_at = int(time.time() + float(token['expires_in'])) if 'expires_in' in token else None
        if save:
            self.save()


class Post(models.Model):
    """Link to an toot (post on mastodon) from one of our notes.

    Mastodon API calls this a status.
    """

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
        return f'{self.note} ({self.connection.server})'

    def post_to_mastodon(self):
        """Issue request to Mastodion instance to create a status."""
        oauth = self.connection.make_oauth()
        r = oauth.post(
            self.connection.server.statuses_url,
            data={
                'status': self.note.text_with_links(),
            },
            headers={
                'Accept': 'application/json',
                'Idempotency-Key': self.note.get_absolute_url(with_host=True),
            },
        )
        r.raise_for_status()
        status = r.json()

        self.their_id = status.get('id')
        self.url = status.get('url')
        self.posted = timezone.now()
        self.save()

