from django.test import TestCase

from ..mimesniff import MimeType

# The algoritm we use is designed to withstand all sorts of twisted variations
# but for Linotak we really only care about recognizing HTML on pages that are
# presumed to be reasonably well-behaved. So the following tests are not as
# thorough as the real HTML5 test suite.


class TestMimeSniff(TestCase):

    def test_can_parse_text_html(self):
        self.assertEqual(MimeType.parse(b"text/html"), MimeType("text", "html"))

    def test_can_parse_text_html_charset(self):
        self.assertEqual(
            MimeType.parse(b"text/html; charset=UTF-8"),
            MimeType("text", "html", {"charset": "UTF-8"}),
        )

    def test_veeby_charset(self):
        self.assertEqual(
            MimeType.parse(b'  Text/HTML ;  CharSet="UTF-8"'),
            MimeType("text", "html", {"charset": "UTF-8"}),
        )

    def test_parse_obscure_charset(self):
        self.assertEqual(
            MimeType.parse(b'application/xhtml+xml; charset="UTF-8"'),
            MimeType("application", "xhtml+xml", {"charset": "UTF-8"}),
        )

    def test_rejects_non_ascii(self):
        self.assertFalse(
            MimeType.parse("soufflé/cheese".encode("windows-1252")),
        )

    def test_rejects_broken_types(self):
        self.assertFalse(MimeType.parse(b"text "))
        self.assertFalse(MimeType.parse(b"text / plain"))
        self.assertFalse(MimeType.parse(b"text/"))
        self.assertFalse(MimeType.parse(b"text/"))

    def test_ignores_broken_parameters(self):
        self.assertEqual(MimeType.parse(b"text/plain;"), MimeType("text", "plain"))
        self.assertEqual(MimeType.parse(b"text/plain; "), MimeType("text", "plain"))
        self.assertEqual(
            MimeType.parse(b"text/plain;charset"), MimeType("text", "plain")
        )
        self.assertEqual(
            MimeType.parse(b"text/plain;charset "), MimeType("text", "plain")
        )
        self.assertEqual(
            MimeType.parse(b"text/plain;charset="), MimeType("text", "plain")
        )
        self.assertEqual(
            MimeType.parse(b"text/plain;charset= "), MimeType("text", "plain")
        )
        self.assertEqual(
            MimeType.parse(b'text/plain;charset = "no whitespace allowed"'),
            MimeType("text", "plain"),
        )

    def test_replaces_non_ascii_characters_with_unicode_fffd(self):
        # This is a bit feeble, but for our purposes non-ASCII characters are never needed.
        self.assertEqual(
            MimeType.parse("text/plain;charset=シフトJIS".encode("shift-jis")),
            MimeType("text", "plain", {"charset": "\ufffdV\ufffdt\ufffdgJIS"}),
        )
        # b'\x83V\x83t\x83g'

    def test_allows_empty_quoted_param(self):
        self.assertEqual(
            MimeType.parse(b'text/plain;charset=""'),
            MimeType("text", "plain", {"charset": ""}),
        )
        # Quoted values also end at the end of the input apparently.
        self.assertEqual(
            MimeType.parse(b'text/plain;charset="'),
            MimeType("text", "plain", {"charset": ""}),
        )
