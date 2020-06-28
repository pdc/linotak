"""View for syndicating to Mastodon.

Making a conenction with OAuth2 requires the following views:

- Form for entering Mastodon user name
  - Form submission extracts instance domain name from @user@domain,
    matches to Instance instance (which must be preconfigured via admin),
    hence generates login URL and redirects to it
- Callback from the Mastodion instance
  - Supplied with code
  - Synchronous call to instance server to conmvert code to access token
  - Stores token in Connection instance

"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render, get_object_or_404
from django.views.generic import DetailView
from django.views.generic.edit import CreateView

from ..notes.views import SeriesMixin
from .models import Connection


class ConnectionCreateView(LoginRequiredMixin, SeriesMixin, CreateView):
    """View to create a Connection instance and start the process of making the connection."""
    model = Connection
    fields = ('series', 'server')

    def get_initial(self):
        return {
            'series': self.series
        }

    def form_valid(self, form):
        connection = form.save()
        authorization_url, state = connection.make_oauth().authorization_url(
            connection.server.authorize_url,
            state=connection.pk,
        )
        return redirect(authorization_url)


def callback(request):
    """Called by Mastodon instance to complete OAuth2 flow."""
    connection = get_object_or_404(Connection, pk=request.GET['state'])
    authorization_response = connection.series.make_absolute_url(request.get_full_path_info())
    oauth = connection.make_oauth()
    token = oauth.fetch_token(
        connection.server.token_url,
        authorization_response=authorization_response,
        client_secret=connection.server.client_secret,
    )

    # Verify it worked and incidentally get user name.
    r = oauth.get(connection.server.verify_credentials_url, headers={'Accept': 'application/json'})
    if r.status_code == 200:
        if acct := r.json().get('acct'):
            connection.name = acct
        connection.save_token(token)
        return redirect('mastodon:connection-detail', pk=connection.pk)

    return render(request, 'mastodon/connection_failed.html', {'response': r, **r.json()})


class ConnectionDetailView(LoginRequiredMixin, SeriesMixin, DetailView):

    model = Connection
