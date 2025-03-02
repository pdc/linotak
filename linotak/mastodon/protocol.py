"""Mastodon protocol.

Implementation of the subset of the Mastodon protocol we use.
Which is essentially declaring apps and writing a status.

A Linotak series optionally is linked to a user on a Mastodon instance.
Notes publishe to the series become public status updates fopr the user.
"""

necessary_scopes = [
    "read:accounts",
    "write:media",
    "write:statuses",
]

authorize_path = "/oauth/authorize"  # GET response_type=code, client_id, client_secret, redirect_uri, scope, and optional state
token_path = "/oauth/token"  # POST authorization_code
revoke_path = "/oauth/revoke"  # POST
verify_credentials_path = "/api/v1/accounts/verify_credentials"  # GET
media_path = "/api/v1/media"  # POST
statuses_path = "/api/v1/statuses"  # POST


def instance_origin(mastodon_user):
    """Given a Mastodon user name, reuturn the HTTP origin of the instance."""
    pass
