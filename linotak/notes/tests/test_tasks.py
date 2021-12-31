"""Test the marshalling of parameters for tasks.

Necessary since JSON cannot encode datetimes.
"""


from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch

from ..models import Locator
from ..tasks import fetch_locator_page
from .. import tasks


class TestFetchLocatorPage(TestCase):
    def test_passes_none_if_never_scanned(self):
        locator = Locator.objects.create(url="https://example.com/1")
        with patch.object(tasks, "fetch_page_update_locator") as func:
            fetch_locator_page(locator.pk, if_not_scanned_since=None)

        func.assert_called_with(locator, if_not_scanned_since=None)

    def test_passes_none_if_never_scanned(self):
        locator = Locator.objects.create(
            url="https://example.com/1", scanned=timezone.now()
        )
        with patch.object(tasks, "fetch_page_update_locator") as func:
            fetch_locator_page(
                locator.pk, if_not_scanned_since=locator.scanned.timestamp()
            )

        func.assert_called_with(locator, if_not_scanned_since=locator.scanned)
