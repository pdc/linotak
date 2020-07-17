from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
import factory
import httpretty
import json
import logging
import requests_oauthlib   # for mocking
from unittest.mock import patch, MagicMock, ANY, call
import time

from ..images.models import Image, Representation
from ..notes.models import LocatorImage
from ..notes.tests.factories import SeriesFactory, NoteFactory, LocatorFactory

from .models import Connection, Post
from .protocol import necessary_scopes
from . import tasks


# class TestInstanceOrigin(TestCase):

#     def test_assumes_https(self):
#         self.assertEqual(instance_origin('@pdc@octodon.social'), 'https://octodon.social')


class ConnectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Connection

    series = factory.SubFactory(SeriesFactory)
    domain = factory.sequence(lambda n: f'mastodon{n}.example.social')
    client_id = factory.sequence(lambda n: f'id_of_client_{n}')
    client_secret = factory.sequence(lambda n: f'*SECRET*OF*{n}*')


class PostFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Post

    note = factory.SubFactory(NoteFactory)
    connection = factory.SubFactory(ConnectionFactory)


class TestConnectionManager(TestCase):

    @httpretty.activate(allow_net_connect=False)
    def test_requests_client_id_and_secret(self):
        series = SeriesFactory(name='name-of-series')
        requests = []

        def request_callback(request, uri, response_headers):
            requests.append(request)
            return 200, response_headers, json.dumps({
                'client_id': 'id-of-client',
                'client_secret': '*SECRET*',
            })
        httpretty.register_uri(
            httpretty.POST,
            'https://masto.example.net/api/v1/apps',
            body=request_callback,
            add_headers={
                'Content-Type': 'application/json',
            },
        )

        with self.settings(NOTES_DOMAIN='example.com'):
            result = Connection.objects.create_connection(series, 'masto.example.net')

        request, = requests
        self.assertEqual(request.parsed_body.get('client_name'), ['name-of-series.example.com'])
        self.assertEqual(request.parsed_body.get('redirect_uris'), ['https://name-of-series.example.com/mastodon/callback'])
        self.assertEqual(request.parsed_body.get('scopes'), [' '.join(necessary_scopes)])
        self.assertEqual(request.parsed_body.get('website'), ['https://name-of-series.example.com/'])

        self.assertEqual(result.series, series)
        self.assertEqual(result.domain, 'masto.example.net')
        self.assertEqual(result.client_id, 'id-of-client')
        self.assertEqual(result.client_secret, '*SECRET*')
        self.assertEqual(result.authorize_url, 'https://masto.example.net/oauth/authorize')


class TestViews(TestCase):
    """Test the views’ plumbing between Server, Connection & OAuth2."""

    def setUp(self):
        get_user_model().objects.create_user(username='alice', password='secret')
        self.client.login(username='alice', password='secret')

    def test_create_view_redirects_to_authentication_url(self):
        series = SeriesFactory(name='slug')

        with patch.object(requests_oauthlib, 'OAuth2Session') as OAuth2Session, \
                patch.object(Connection.objects, 'create_connection') as create_connection, \
                self.settings(NOTES_DOMAIN='notes.example.org'):
            create_connection.side_effect \
                = lambda s, d: ConnectionFactory(series=s, domain=d, client_id='id-of-client', client_secret='*SECRET*')
            oauth = OAuth2Session.return_value
            oauth.authorization_url.return_value = 'https://mast.example.com/auth?this=that', '*STATE*'

            r = self.client.post('/mastodon/connections/add', {'series': series.pk, 'domain': 'mast.example.com'}, follow=False)

        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, 'https://mast.example.com/auth?this=that')
        connection = Connection.objects.get(series=series, domain='mast.example.com')
        self.assertEqual(connection.client_id, 'id-of-client')
        self.assertEqual(connection.client_secret, '*SECRET*')
        OAuth2Session.assert_called_with(
            'id-of-client',
            redirect_uri='https://slug.notes.example.org/mastodon/callback',
            scope=necessary_scopes,
        )
        oauth.authorization_url.assert_called_with(
            'https://mast.example.com/oauth/authorize',
            state=connection.pk,
        )

    def test_callback_processes_access_code_stores_token(self):
        series = SeriesFactory(name='slug')
        connection = Connection.objects.create(series=series, domain='mast.example.com', client_id='id_of_client', client_secret='*SECRET*')
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
            oauth.get.return_value = mock_json_response({'acct': 'alice'})
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
            client_secret='*SECRET*',
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

    def test_callback_processes_access_code_sans_refresh_token(self):
        series = SeriesFactory(name='slug')
        connection = Connection.objects.create(series=series, domain='mast.example.com')

        with patch.object(requests_oauthlib, 'OAuth2Session') as OAuth2Session, \
                self.settings(NOTES_DOMAIN='notes.example.net'):
            oauth = OAuth2Session.return_value
            oauth.fetch_token.return_value = {
                'access_token': '*ACCESS*TOKEN*',
                'token_type': 'Bearer',
                # Turns out real Mastodon servers do not supply a refresh token.
            }
            oauth.get.return_value = mock_json_response({'acct': 'alice'})
            self.client.get('/mastodon/callback', {'state': connection.pk, 'code': '...CODE...'}, follow=False)

        connection.refresh_from_db()
        self.assertEqual(connection.access_token, '*ACCESS*TOKEN*')
        self.assertFalse(connection.refresh_token)
        self.assertFalse(connection.expires_at)


class TestConnection(TestCase):

    def test_uses_token_to_create_oauth_client(self):
        subject = ConnectionFactory(access_token='*ACCESS*TOKEN*')

        with patch.object(requests_oauthlib, 'OAuth2Session') as OAuth2Session, self.settings(NOTES_DOMAIN='example.com'):
            oauth = OAuth2Session.return_value
            result = subject.make_oauth()

        self.assertEqual(result, oauth)
        OAuth2Session.assert_called_with(
            subject.client_id,
            token={
                'access_token': '*ACCESS*TOKEN*',
                'token_type': 'Bearer',
                # No refresh token because Mastosdon doesn’t use them.
            },
        )


class TestPost(TestCase):
    """Test the Connection instances know how to do stuff."""
    def setUp(self):
        logging.disable(logging.CRITICAL)

        self.series = SeriesFactory(name='slug')
        self.connection = ConnectionFactory(series=self.series, domain='mast.example.com', name='spoo', access_token='*ACCESS*TOKEN*')

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_posts_text_of_note_to_mastodon(self):
        self.create_note_with_locator()

        with patch.object(requests_oauthlib, 'OAuth2Session') as OAuth2Session, self.settings(NOTES_DOMAIN='example.com'):
            oauth = OAuth2Session.return_value
            oauth.post.return_value = mock_json_response({
                'id': '134269',
                'url': 'https://mast.example.com/@spoo/134269'
            })
            self.post.post_to_mastodon()

        oauth.post.assert_called_with(
            'https://mast.example.com/api/v1/statuses',
            json={
                'status': 'Hello, world!\n\n#greeting #planet\n\nhttps://other.example.com/1',
            },
            headers={
                'Accept': 'application/json',
                'Idempotency-Key': f'https://slug.example.com/{self.note.pk}',
            },
        )
        self.post.refresh_from_db()
        self.assertEqual(self.post.their_id, '134269')
        self.assertEqual(self.post.url, 'https://mast.example.com/@spoo/134269')

    def test_does_not_post_a_second_time(self):
        post = Post.objects.create(posted=timezone.now())

        with patch.object(requests_oauthlib, 'OAuth2Session') as OAuth2Session:
            post.post_to_mastodon()

        self.assertFalse(OAuth2Session.called)

    def test_posts_main_image_of_subject(self):
        self.create_note_with_locator()
        self.with_image_with_representation()

        with patch.object(requests_oauthlib, 'OAuth2Session') as OAuth2Session,  \
                self.settings(NOTES_DOMAIN='example.com'):
            oauth = OAuth2Session.return_value
            oauth.post.side_effect = [
                mock_json_response({'id': '100001'}),  # Response when creating media.
                mock_json_response({  # Response when creating post.
                    'id': '200002',
                    'url': 'https://mast.example.com/@spoo/134269'
                }),
            ]
            self.post.post_to_mastodon()

            oauth.post.assert_has_calls([
                call(
                    'https://mast.example.com/api/v1/media',
                    files={'file': (ANY, ANY, 'image/jpeg')},
                ),
                call(
                    'https://mast.example.com/api/v1/statuses',
                    json={
                        'status': 'Hello, world!\n\n#greeting #planet\n\nhttps://other.example.com/1',
                        'media_ids': ['100001'],
                    },
                    headers={
                        'Accept': 'application/json',
                        'Idempotency-Key': f'https://slug.example.com/{self.note.pk}',
                    },
                ),
            ])
            # Check contents of stream sent to create image.
            _, kwargs = oauth.post.call_args_list[0]
            _, stream, _ = kwargs['files']['file']
            self.assertEqual(stream.read(), b'*file*content*')
            stream.close()

    def test_adds_sensitive_flag_to_post_of_niote_with_locator_with_sensitive_flag(self):
        self.create_note_with_locator(sensitive=True)
        self.with_image_with_representation()

        with patch.object(requests_oauthlib, 'OAuth2Session') as OAuth2Session,  \
                self.settings(NOTES_DOMAIN='example.com'):
            oauth = OAuth2Session.return_value
            oauth.post.side_effect = [
                mock_json_response({'id': '100001'}),  # Response when creating media.
                mock_json_response({  # Response when creating post.
                    'id': '200002',
                    'url': 'https://mast.example.com/@spoo/134269'
                }),
            ]
            self.post.post_to_mastodon()

            oauth.post.assert_has_calls([
                call(
                    'https://mast.example.com/api/v1/media',
                    files={'file': (ANY, ANY, 'image/jpeg')},
                ),
                call(
                    'https://mast.example.com/api/v1/statuses',
                    json={
                        'status': 'Hello, world!\n\n#greeting #planet\n\nhttps://other.example.com/1 (nsfw)',
                        'media_ids': ['100001'],
                        'sensitive': True,
                    },
                    headers={
                        'Accept': 'application/json',
                        'Idempotency-Key': f'https://slug.example.com/{self.note.pk}',
                    },
                ),
            ])
            # Check contents of stream sent to create image.
            _, kwargs = oauth.post.call_args_list[0]
            _, stream, _ = kwargs['files']['file']
            self.assertEqual(stream.read(), b'*file*content*')
            stream.close()

    def create_note_with_locator(self, **kwargs):
        self.locator = LocatorFactory(url='https://other.example.com/1', **kwargs)
        self.note = NoteFactory(
            series=self.series,
            text='Hello, world!',
            tags=['greeting', 'planet'],
            subjects=[self.locator],
            published=timezone.now()
        )
        self.post = self.note.mastodon_posts.get()

    def with_image_with_representation(self):
        """Arrange that create_representation succeeds without running external commands."""
        self.image = Image.objects.create(width=1920, height=1080)
        representation = Representation.objects.create(
            image=self.image,
            media_type='image/jpeg',
            width=1280,
            height=(1280 * 1080 // 1920),
            is_cropped=False,
        )
        representation.content.save('spoo.jpeg', ContentFile(b'*file*content*'))
        LocatorImage.objects.create(locator=self.locator, image=self.image)


class TestHandleNotePostSave(TransactionTestCase):
    """Test the queueing of task when note saved."""

    # Take care not to create entities outside of a transaction in tests in this class!

    def test_does_nothing_if_unpublished(self):
        with self.settings(MASTODON_POST_STATUSES=True), patch.object(tasks, 'post_post_to_mastodon') as post_post_to_mastodon:
            with transaction.atomic():
                connection = ConnectionFactory(access_token='X')
                note = NoteFactory(series=connection.series)

            self.assertFalse(post_post_to_mastodon.delay.called)
            self.assertFalse(Post.objects.filter(note=note, connection=connection).exists())

    def test_queues_post_if_published(self):
        with self.settings(MASTODON_POST_STATUSES=True), patch.object(tasks, 'post_post_to_mastodon') as post_post_to_mastodon:
            with transaction.atomic():
                connection = ConnectionFactory(access_token='X')
                note = NoteFactory(series=connection.series)

                note.published = timezone.now()
                note.save()

                self.assertFalse(post_post_to_mastodon.delay.called)

            post = Post.objects.get(note=note, connection=connection)
            post_post_to_mastodon.delay.assert_called_once_with(post.pk)

    def test_doesnt_queue_if_already_posted(self):
        with patch.object(tasks, 'post_post_to_mastodon') as post_post_to_mastodon:
            with transaction.atomic():
                connection = ConnectionFactory(access_token='X')
                note = NoteFactory(series=connection.series, published=timezone.now())
                post = Post.objects.get(note=note, connection=connection)
                post.posted = timezone.now()
                post.save()

                with self.settings(MASTODON_POST_STATUSES=True):
                    note.save()

            self.assertFalse(post_post_to_mastodon.delay.called)


def mock_json_response(obj):
    """Given an object, create a mock Requests response."""
    return MagicMock(status_code=200, json=MagicMock(return_value=obj))
