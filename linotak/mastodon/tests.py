from django.test import TestCase

from .protocol import instance_origin


class TestInstanceOrigin(TestCase):

    def test_assumes_https(self):
        self.assertEqual(instance_origin('@pdc@octodon.social'), 'https://octodon.social')
