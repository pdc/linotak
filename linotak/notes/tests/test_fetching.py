from unittest.mock import patch

import responses
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from ...fetching import clean_url, fetch, requests, socket, validators


class TestCheckURLFetchable(SimpleTestCase):

    def test_validators_url(self):
        self.assertTrue(
            validators.url(
                "https://community.owasp.org/attacks/Server_Side_Request_Forgery"
            )
        )
        self.assertTrue(
            validators.url(
                "https://community.owasp.org/attacks/Server_Side_Request_Forgery",
                skip_ipv6_addr=True,
                skip_ipv4_addr=True,
                strict_query=True,
                private=False,
                validate_scheme=lambda s: s in {"http", "https"},
            )
        )

    def test_accepts_real_external_url(self):
        url = "https://community.owasp.org/attacks/Server_Side_Request_Forgery"
        result = clean_url(url)
        self.assertEqual(result, url)

    def test_rejects_empty_or_blank(self):
        self.assertRaises(ValidationError, lambda: clean_url(None))
        self.assertRaises(ValidationError, lambda: clean_url(""))
        self.assertRaises(ValidationError, lambda: clean_url("  "))

    def test_rejects_file_and_ftp(self):
        self.assertRaises(ValidationError, lambda: clean_url("ftp://foobar.dk"))
        self.assertRaises(ValidationError, lambda: clean_url("file:///etc/passwd"))

    def test_rejects_local(self):
        # Blocklist from https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html#deny-list-last-resort
        self.assertRaises(ValidationError, lambda: clean_url("http://localhost:8000"))
        self.assertRaises(ValidationError, lambda: clean_url("https://localhost"))
        self.assertRaises(ValidationError, lambda: clean_url("http://127.0.0.1"))
        self.assertRaises(ValidationError, lambda: clean_url("http://0.0.0.0"))
        self.assertRaises(ValidationError, lambda: clean_url("http://[::1/128]"))
        self.assertRaises(ValidationError, lambda: clean_url("http://169.254.169.254"))
        # RFC1918 Private – 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
        self.assertRaises(ValidationError, lambda: clean_url("http://10.0.0.1"))
        self.assertRaises(ValidationError, lambda: clean_url("http://172.16.1.2"))
        self.assertRaises(ValidationError, lambda: clean_url("http://192.168.1.2"))
        # Multicast – 224.0.0.0/4, ff00::/8
        self.assertRaises(ValidationError, lambda: clean_url("http://224.0.0.1"))

    def test_rejects_ip6_constant(self):
        self.assertRaises(
            ValidationError, lambda: clean_url("https://[2a01:4f8:c013:4422::1]/")
        )

    def test_rejects_ip4_constant(self):
        self.assertRaises(ValidationError, lambda: clean_url("https://188.245.56.86/"))

    def test_rejects_simple_names(self):
        self.assertRaises(ValidationError, lambda: clean_url("http://frog"))
        self.assertRaises(ValidationError, lambda: clean_url("http://smash-pumpkin"))

    def test_rejects_when_resolves_to_loopback_addr(self):
        # Given the hostname in question resolves to a loopback IP address …
        with patch.object(socket, "getaddrinfo") as getaddrinfo:
            getaddrinfo.return_value = [
                (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", 80, 0, 0)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80)),
            ]

            # Then the URL with that hostname does not validate.
            self.assertRaises(
                ValidationError,
                lambda: clean_url("https://narnia.example.com/foop"),
            )

        getaddrinfo.assert_called_once_with(
            "narnia.example.com",
            None,
            proto=socket.IPPROTO_TCP,
            flags=socket.AI_ALL,
        )


class TestFetch(SimpleTestCase):
    @responses.activate
    def test_follows_redirects(self):
        with patch.object(socket, "getaddrinfo") as getaddrinfo:
            # Given a URL that redirects to another URL …
            responses.get(
                "https://narnia.example.com/foo",
                status=302,
                headers={"Location": "https://liliput.example.com/bar"},
            )
            responses.get("https://liliput.example.com/bar", body="Hello, world!")
            getaddrinfo.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("188.245.56.86", 80)),
            ]
            result = fetch("https://narnia.example.com/foo")

        # Then it returns the final URL.
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.text, "Hello, world!")

    @responses.activate
    def test_rejects_when_redirected_to_somewhere_bad(self):
        with patch.object(socket, "getaddrinfo") as getaddrinfo:
            # Given a URL that redirects to a disguised local address …
            responses.get(
                "https://narnia.example.com/foo",
                status=302,
                headers={"Location": "https://liliput.example.com/bar"},
            )
            responses.get("https://liliput.example.com/bar", body="Hello, world!")

            getaddrinfo.side_effect = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("188.245.56.86", 80)),
            ], [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80)),
            ]

            # Then it refuses to download it.
            with self.assertRaises(ValidationError):
                fetch("https://narnia.example.com/foo")

    @responses.activate
    def test_passes_in_kwargs(self):
        with (
            patch.object(socket, "getaddrinfo") as getaddrinfo,
            patch.object(requests, "get") as requests_get,
            self.settings(NOTES_FETCH_AGENT="agent-string/1.1"),
        ):
            # Given a URL with stuff  …
            responses.get("https://liliput.example.com/bar", body="Hello, world!")

            getaddrinfo.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("188.245.56.86", 80)),
            ]

            # When fetched with kwargs …
            fetch("https://liliput.example.com/bar", stream=True)

        # Then the kwargs are passed in.
        requests_get.assert_called_with(
            "https://liliput.example.com/bar",
            allow_redirects=False,
            headers={"User-Agent": "agent-string/1.1"},
            stream=True,
        )

    @responses.activate
    def test_merges_headers(self):
        with (
            patch.object(socket, "getaddrinfo") as getaddrinfo,
            patch.object(requests, "get") as requests_get,
            self.settings(NOTES_FETCH_AGENT="agent-string/1.1"),
        ):
            # Given a URL with stuff  …
            responses.get("https://liliput.example.com/bar", body="Hello, world!")

            getaddrinfo.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("188.245.56.86", 80)),
            ]

            # When fetched with kwargs …
            fetch(
                "https://liliput.example.com/bar",
                headers={"Accept": "application/json"},
            )

        # Then the kwargs are passed in.
        requests_get.assert_called_with(
            "https://liliput.example.com/bar",
            allow_redirects=False,
            headers={"Accept": "application/json", "User-Agent": "agent-string/1.1"},
        )
