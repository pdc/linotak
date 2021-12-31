from django.test import TestCase
from pathlib import Path
import shutil
import tempfile

from .pages import Page


class TestPageFormattedText(TestCase):
    def test_extracts_title_from_headers(self):
        result = Page.parse("pagename", "Title: Title of Page\n\nText of page\n")

        self.assertEqual(result.name, "pagename")
        self.assertEqual(result.title, "Title of Page")
        self.assertEqual(result.text, "Text of page\n")

    def test_can_format_markdown(self):
        page = Page(
            "nameofpage", "Title of Page", "# Heading\nText of page\n\nSecond par"
        )

        result = page.formatted()

        self.assertEqual(
            result,
            "<h1>Heading</h1>\n<div>\n<p>Text of page</p>\n<p>Second par</p>\n</div>",
        )

    def test_replaces_obvious_tags(self):
        page = Page("nameofpage", "Title of Page", "# About {{ series.title }}\nText")
        page.set_context({"series": {"title": "Title of Series"}})

        result = page.formatted()

        self.assertEqual(
            result, "<h1>About Title of Series</h1>\n<div>\n<p>Text</p>\n</div>"
        )


class TestPageFinding(TestCase):
    """Test we can find the content dir."""

    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Remove the directory after the test
        shutil.rmtree(self.test_dir)

    def test_defaults_to_app_content(self):
        result = Page.content_root()

        self.assertEqual(result, Path(__file__).parent / "content")

    def test_can_set_with_setting(self):
        custom_root = Path(self.test_dir) / "foo"
        with self.settings(ABOUT_CONTENT_ROOT=str(custom_root)):
            result = Page.content_root()

        self.assertEqual(result, custom_root)

    def test_can_find_file_for_page(self):
        content_root = Path(self.test_dir)
        with open(content_root / "burble.mmd", "w", encoding="UTF-8") as output:
            output.write("Title: Hello\n\nWorld")

        with self.settings(ABOUT_CONTENT_ROOT=content_root):
            result = Page.find_with_name("burble")

        self.assertTrue(result)
        self.assertEqual(result.name, "burble")
        self.assertEqual(result.title, "Hello")
        self.assertEqual(result.text, "World")

    def test_can_find_file_for_index(self):
        content_root = Path(self.test_dir)
        with open(content_root / "index.mmd", "w", encoding="UTF-8") as output:
            output.write("Title: Hello\n\nWorld")

        with self.settings(ABOUT_CONTENT_ROOT=content_root):
            result = Page.find_with_name("")

        self.assertTrue(result)
        self.assertFalse(result.name)
        self.assertEqual(result.title, "Hello")
        self.assertEqual(result.text, "World")
