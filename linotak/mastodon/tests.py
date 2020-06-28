from django.contrib.auth import get_user_model
from django.test import TestCase
import factory
import requests_oauthlib   # for mocking
from unittest.mock import patch, MagicMock
import time

from ..notes.tests.factories import SeriesFactory

from .models import Server, Connection
from .protocol import necessary_scopes


# class TestInstanceOrigin(TestCase):

#     def test_assumes_https(self):
#         self.assertEqual(instance_origin('@pdc@octodon.social'), 'https://octodon.social')


class ServerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Server

    name = factory.sequence(lambda n: f'mastodon{n}.example.social')
    client_id = factory.sequence(lambda n: f'id_of_client_{n}')
    client_secret = factory.sequence(lambda n: f'*SECRET*OF*{n}*')


class ConnectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Connection

    series = factory.SubFactory(SeriesFactory)
    server = factory.SubFactory(ServerFactory)


class TestConnectionCreation(TestCase):
    """Test the plumbinmg between Server, Connection & Oauth2."""

    def setUp(self):
        get_user_model().objects.create_user(username='alice', password='secret')
        self.client.login(username='alice', password='secret')

    def test_redirects_to_authentication_url(self):
        series = SeriesFactory(name='slug')
        server = ServerFactory(name='mast.example.com', client_id='id_of_client')

        with patch.object(requests_oauthlib, 'OAuth2Session') as OAuth2Session, self.settings(NOTES_DOMAIN='notes.example.org'):
            oauth = OAuth2Session.return_value
            oauth.authorization_url.return_value = 'https://mast.example.com/auth?this=that', '*STATE*'

            r = self.client.post('/mastodon/connections/add', {'series': series.pk, 'server': server.pk}, follow=False)

        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, 'https://mast.example.com/auth?this=that')
        self.assertTrue(Connection.objects.filter(series=series, server=server).exists())
        OAuth2Session.assert_called_with(
            'id_of_client',
            redirect_uri='https://slug.notes.example.org/mastodon/callback',
            scope=necessary_scopes,
        )
        oauth.authorization_url.assert_called_with(
            'https://mast.example.com/oauth/authorize',
            state=Connection.objects.get().pk,
        )

    def test_processes_access_code_stores_token(self):
        series = SeriesFactory(name='slug')
        server = ServerFactory(name='mast.example.com', client_id='id_of_client', client_secret='...SECRET...')
        connection = Connection.objects.create(series=series, server=server)
        now = time.time()

        with patch.object(requests_oauthlib, 'OAuth2Session') as OAuth2Session, \
                self.settings(NOTES_DOMAIN='notes.example.net'),\
                patch.object(time, 'time', return_value=now):
            oauth = OAuth2Session.return_value
            oauth.fetch_token.return_value = {
                'access_token': '*ACCESS*TOKEN*',
                'refresh_token': '*REFRESH*TOKEN*',
                'token_type': 'Bearer',
                'expires_in': '3600',
            }
            oauth.get.return_value = MagicMock(status_code=200, json=MagicMock(return_value={'acct': 'alice'}))
            r = self.client.get('/mastodon/callback', {'state': connection.pk, 'code': '...CODE...'}, follow=False)

        OAuth2Session.assert_called_with(
            'id_of_client',
            redirect_uri='https://slug.notes.example.net/mastodon/callback',
            scope=necessary_scopes,
        )
        authorization_response = f'https://slug.notes.example.net/mastodon/callback?state={connection.pk}&code=...CODE...'
        oauth.fetch_token.assert_called_with(
            'https://mast.example.com/oauth/token',
            authorization_response=authorization_response,
            client_secret='...SECRET...',
        )
        oauth.get.assert_called_with(
            'https://mast.example.com/api/v1/accounts/verify_credentials',
            headers={
                'Accept': 'application/json',
            }
        )
        connection.refresh_from_db()
        self.assertEqual(connection.name, 'alice')
        self.assertEqual(connection.access_token, '*ACCESS*TOKEN*')
        self.assertEqual(connection.refresh_token, '*REFRESH*TOKEN*')
        self.assertEqual(connection.expires_at, int(now + 3600.0))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, f'/mastodon/connections/{connection.pk}')

    def test_processes_access_code_sans_refresh_token(self):
        series = SeriesFactory(name='slug')
        server = ServerFactory(name='mast.example.com')
        connection = Connection.objects.create(series=series, server=server)

        with patch.object(requests_oauthlib, 'OAuth2Session') as OAuth2Session, \
                self.settings(NOTES_DOMAIN='notes.example.net'):
            oauth = OAuth2Session.return_value
            oauth.fetch_token.return_value = {
                'access_token': '*ACCESS*TOKEN*',
                'token_type': 'Bearer',
                # Turns out real Mastodon servers do not supply a refresh token.
            }
            oauth.get.return_value = MagicMock(status_code=200, json=MagicMock(return_value={'acct': 'alice'}))
            self.client.get('/mastodon/callback', {'state': connection.pk, 'code': '...CODE...'}, follow=False)

        connection.refresh_from_db()
        self.assertEqual(connection.access_token, '*ACCESS*TOKEN*')
        self.assertFalse(connection.refresh_token)
        self.assertFalse(connection.expires_at)


class TestConnection(TestCase):
    """Test the Connection instances know how to do stuff."""

    def test_uses_token_to_create_oauth_client(self):
        connection = ConnectionFactory(access_token='*ACCESS*TOKEN*')

        with patch.object(requests_oauthlib, 'OAuth2Session') as OAuth2Session, self.settings(NOTES_DOMAIN='example.com'):
            oauth = OAuth2Session.return_value
            result = connection.make_oauth()

        self.assertEqual(result, oauth)
        OAuth2Session.assert_called_with(
            connection.server.client_id,
            token=connection.access_token,
        )
