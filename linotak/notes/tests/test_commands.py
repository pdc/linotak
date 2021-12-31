import io
import os

from django.core.management import call_command
from django.test import TestCase


class TestLinotakScanCommand(TestCase):
    """Test linotakscan command."""

    def test_feeds_file_to_page_scanner(self):
        text = self.call_command("simple.html")
        self.assertTrue("Title('Test file')" in text)

    def test_sets_base_uri(self):
        text = self.call_command("simple.html", "--base", "http://example.com/foo/bar")
        self.assertTrue("Link({'webmention'}, 'http://example.com/webention')" in text)

    def call_command(self, file_name, *args, **kwargs):
        file_path = os.path.join(os.path.dirname(__file__), "data", file_name)
        output = io.StringIO()
        call_command("linotakscan", file_path, *args, stdout=output, **kwargs)
        return output.getvalue()
