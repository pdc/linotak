"""Tests for middleware."""

from django.test import TestCase
from django.http import HttpRequest
from unittest.mock import MagicMock

from ..middleware import SubdomainSeriesMiddleware


class TestSubdomainSeriesMiddleware(TestCase):
    def test_passes_request_through(self):
        with self.settings(NOTES_DOMAIN="example.org"):
            get_response = MagicMock(name="get_response")
            get_response.return_value = MagicMock(name="**RESPONSE**")
            middleware = SubdomainSeriesMiddleware(get_response)

            request = self.make_request_with_domain()
            response = middleware(request)

            self.assertIs(response, get_response.return_value)
            get_response.assert_called_once_with(request)

    def test_sets_series_name_if_subdomain(self):
        with self.settings(NOTES_DOMAIN="example.org"):
            middleware = SubdomainSeriesMiddleware(MagicMock())

            request = self.make_request_with_domain("foo.example.org")
            middleware(request)

        self.assertEqual(request.series_name, "foo")

    def test_sets_series_name_if_subdomain_with_port(self):
        with self.settings(NOTES_DOMAIN="example.org:8080"):
            middleware = SubdomainSeriesMiddleware(MagicMock())

            request = self.make_request_with_domain("foo.example.org:8080")
            middleware(request)

        self.assertEqual(request.series_name, "foo")

    def make_request_with_domain(self, host="example.com"):
        request = HttpRequest()
        request.META["HTTP_HOST"] = host
        return request
