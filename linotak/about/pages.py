"""Find pages in the content directory."""

from email.parser import Parser
from io import StringIO
from pathlib import Path

import markdown
from django.apps import apps
from django.conf import settings
from django.template import engines
from django.utils.safestring import mark_safe

# This module assumes a local file system: shoukd I be using the generic storage API instead?


class Page:
    """One page of text that can be displayed."""

    request = None

    def __init__(self, name, title, text):
        """Create an instance with this title and text.

        Arguments --
            title (string) -- title of the page (may have site name appended)
            text (string) -- the Markdown-encoded content of this page
        """
        self.name = name
        self.title = title
        self.text = text
        self.context = {}

    @classmethod
    def parse(cls, name, input):
        """Scan this text for headers and Markdown body."""
        if isinstance(input, str):
            input = StringIO(input)
        message = Parser().parse(input)
        title = message["title"]
        text = message.get_payload()
        return Page(name, title, text)

    @classmethod
    def content_root(cls):
        result = getattr(settings, "ABOUT_CONTENT_ROOT", None)
        if result:
            return Path(result)
        config = apps.get_app_config("about")
        return Path(config.path) / "content"

    @classmethod
    def find_with_name(cls, name):
        path = cls.content_root() / ((name or "index") + ".mmd")
        with open(path, "r", encoding="UTF-8") as f:
            return cls.parse(name, f)

    def set_context(self, context, request=None):
        """Add variables to be used when expanding tempalted pages."""
        self.context.update(context)
        if request is not None:
            self.request = request

    @mark_safe
    def formatted(self):
        """Text of this page, formatted with Markdown."""
        django_engine = engines["django"]
        template = django_engine.from_string(self.text)
        text = template.render(self.context)
        formatted = markdown.markdown(text, output="HTML5")
        pos = formatted.find("</h1>")
        if pos >= 0:
            formatted = (
                formatted[: pos + 5] + "\n<div>" + formatted[pos + 5 :] + "\n</div>"
            )
        return formatted
