from datetime import timedelta
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.test import TestCase
from django.utils import timezone
import httpretty
import os

from .models import Image


# How we obtain real test files:
data_dir = os.path.join(os.path.dirname(__file__), 'test-data')
data_storage = FileSystemStorage(location=data_dir)


class TestImageSniff(TestCase):
    """Test Image.sniff."""

    def setUp(self):
        self.images_to_delete = []

    def tearDown(self):
        for image in self.images_to_delete:
            image.cached_data.delete()

    def create_image_with_data(self, file_name):
        """Create an image and remember to delete it."""
        with open(os.path.join(data_dir, file_name), 'rb') as input:
            data = input.read()
        self.image = Image.objects.create(data_url='https://example.org/1')
        self.image.cached_data.save('test_file', ContentFile(data), save=True)
        # Intentionally don’t give it a ‘.png’ extension.
        self.images_to_delete.append(self.image)
        return self.image

    def test_can_get_width_and_height_of_png(self):
        image = self.create_image_with_data('im.png')

        image.sniff()

        self.assertEqual(image.media_type, 'image/png')
        self.assertEqual(image.width, 69)
        self.assertEqual(image.height, 42)

    def test_can_get_width_and_height_of_jpeg(self):
        image = self.create_image_with_data('37x57.jpeg')

        image.sniff()

        self.assertEqual(image.media_type, 'image/jpeg')
        self.assertEqual(image.width, 37)
        self.assertEqual(image.height, 57)


class TestImageRetrieve(TestCase):
    """Test Image.retrieve."""

    image = None  # Overridden in most tests.

    def tearDown(self):
        if self.image and self.image.cached_data:
            self.image.cached_data.delete()

    @httpretty.activate(allow_net_connect=False)
    def test_can_retrive_image_and_sniff(self):
        self.given_image_with_data()

        self.image.retrieve_data(if_not_retrieved_since=None)

        self.then_retrieved_and_sniffed()

    @httpretty.activate(allow_net_connect=False)
    def test_does_not_retrieve_if_retrieved(self):
        then = timezone.now() - timedelta(hours=1)
        self.image = Image.objects.create(data_url='https://example.com/1', retrieved=then)

        self.image.retrieve_data(if_not_retrieved_since=None)

        # Attempting to download will cause HTTPretty to complain.

    @httpretty.activate(allow_net_connect=False)
    def test_will_retrieve_if_retrieved_in_the_past(self):
        then = timezone.now() - timedelta(days=30)
        self.given_image_with_data(retrieved=then)

        self.image.retrieve_data(if_not_retrieved_since=then)

        self.then_retrieved_and_sniffed()

    @httpretty.activate(allow_net_connect=False)
    def test_does_not_retrieve_if_retrieved_later(self):
        then = timezone.now() - timedelta(hours=1)
        earlier = timezone.now() - timedelta(hours=2)
        self.image = Image.objects.create(data_url='https://example.com/1', retrieved=then)

        self.image.retrieve_data(if_not_retrieved_since=earlier)

        # Attempting to download will cause HTTPretty to complain.

    def given_image_with_data(self, **kwargs):
        img_src = 'http://example.com/2'
        with open(os.path.join(data_dir, 'im.png'), 'rb') as input:
            self.data = input.read()
        self.image = Image.objects.create(data_url=img_src, **kwargs)
        httpretty.register_uri(
            httpretty.GET, 'http://example.com/2',
            body=self.data,
            add_headers={
                'Content-Type': 'image/png'
            },
        )

    def then_retrieved_and_sniffed(self):
        self.assertEqual(self.image.width, 69)
        self.assertEqual(self.image.height, 42)
        with self.image.cached_data.open() as f:
            actual = f.read()
        self.assertEqual(actual, self.data)

# class TestTasks(TestCase):


# class TestImageCreationTriggersRetrieve(TestCase):
#     """Test locator_fetch_page_update."""

#     def test_queues_fetch_when_locator_created(self):
#         """Test locator_fetch_page_update queues fetch when locator created."""
#         with self.settings(NOTES_FETCH_LOCATORS=True), patch.object(signals, 'fetch_locator_page') as fetch_locator_page:
#             locator = Image.objects.create(data_url='https://example.com/1')

#             fetch_locator_page.delay.assert_called_once_with(locator.pk, if_not_scanned_since=None)

#     def test_doesnt_queue_if_settings_not_set(self):
#         """Test locator_fetch_page_update doesnt queue if settings not set."""
#         with self.settings(NOTES_FETCH_LOCATORS=False), patch.object(signals, 'fetch_locator_page') as fetch_locator_page:
#             Image.objects.create(data_url='https://example.com/1')

#             self.assertFalse(fetch_locator_page.delay.called)

#     def test_doesnt_queue_if_not_newly_created(self):
#         """Test locator_fetch_page_update doesnt queue if not newly created"""
#         with self.settings(NOTES_FETCH_LOCATORS=True), patch.object(signals, 'fetch_locator_page') as fetch_locator_page:
#             locator = Image.objects.create(data_url='https://example.com/1')
#             locator.title = 'FOO'
#             locator.save()

#             fetch_locator_page.delay.assert_called_once_with(locator.pk, if_not_scanned_since=None)
