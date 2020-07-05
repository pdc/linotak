
"""Mastodon protocol.

Implementation of the subset of the Mastodon protocol we use.
Which is essentially declaring apps and writing a status.

A Linotak series optionally is linked to a user on a Mastodon instance.
Notes publishe to the series become public status updates fopr the user.
"""

from django.urls import reverse


necessary_scopes = [
    'read:accounts',
    'write:statuses',
]

authorize_path = '/oauth/authorize'  # GET response_type=code, client_id, client_secret, redirect_uri, scope, and optional state
token_path = '/oauth/token'  # POST authorization_code
revoke_path = '/oauth/revoke'  # POST
verify_credentials_path = '/api/v1/accounts/verify_credentials'  # GET
statuses_path = '/api/v1/statuses'  # POST


def instance_origin(mastodon_user):
    """Given a Mastodon user name, reuturn the HTTP origin of the instance."""
    pass


def create_app(series, mastodon_user):
    """Create an app on Mastodon."""
    data = {
        'client_name': series.title,
        'redirect_urls': reverse('mastodon.callback'),
        'scopes': ' '.join(necessary_scopes),
        'website': series.make_absolute_url(series.get_absolute_url()),
    }
    r = requests.get()
