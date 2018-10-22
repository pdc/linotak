import io
import os
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from notes import scanner


class TestLinotakScanCommand(TestCase):
    """Test linotakscan command."""

    def test_feeds_file_to_page_scanner(self):
        file_path = os.path.join(os.path.dirname(__file__), 'data/simple.html')
        output = io.StringIO()
        call_command('linotakscan', file_path, stdout=output)

        text = output.getvalue()
        self.assertTrue("Title('Test file')" in text)
