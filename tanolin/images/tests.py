from datetime import timedelta
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.test import TestCase
from django.utils import timezone
import httpretty
import os
import struct
from unittest.mock import patch

from .models import Image, _sniff
from . import signal_handlers  # For mocking


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


class TestSignalHandler(TestCase):
    """Test the signal handler."""

    # The retireval of image data is suppressed during testing,
    # so in these tests we need to explictly enable it.

    def test_queues_retrieve_when_image_created(self):
        """Test signal handler queues retrieve when image created."""
        with self.settings(IMAGES_FETCH_DATA=True), patch.object(signal_handlers, 'retrieve_image_data') as retrieve_image_data:
            self.image = Image.objects.create(data_url='https://example.com/1')

        retrieve_image_data.delay.assert_called_with(self.image.pk, if_not_retrieved_since=None)

    def test_doesnt_queue_retrieve_when_retrieved_is_set(self):
        """Test signal handler doesnt queue retrieve when retrieved is set."""
        with self.settings(IMAGES_FETCH_DATA=True), patch.object(signal_handlers, 'retrieve_image_data') as retrieve_image_data:
            self.image = Image.objects.create(data_url='https://example.com/1', retrieved=timezone.now())

        self.assertFalse(retrieve_image_data.delay.called)


class ImageTestMixin:

    image = None

    def tearDown(self):
        if self.image and self.image.cached_data:
            for rep in self.image.representations.all():
                rep.content.delete()
            self.image.cached_data.delete()

    def given_image_with_data(self, file_name, **kwargs):
        with open(os.path.join(data_dir, file_name), 'rb') as input:
            self.data = input.read()
        self.image = Image.objects.create(data_url='http://example.com/69', **kwargs)
        self.image.cached_data.save('test.png', ContentFile(self.data))
        self.image.sniff()
        self.image.save()


class TestImageCreateSquareRepresentation(ImageTestMixin, TestCase):

    def test_can_create_square_from_rect(self):
        self.given_image_with_data('im.png')

        self.image.create_square_representation(32)

        # convert - -resize '^32x32>' -gravity center -extent 32x32 - < tanolin/images/test-data/im.png > tanolin/images/test-data/im-32sq.png
        self.assertEqual(self.image.representations.count(), 1)
        rep = self.image.representations.all()[0]
        self.assert_representation(rep, 'image/png', 32, 32, is_cropped=True)
        self.assert_same_PNG_as_file(rep, 'im-32sq.png')

    def test_doesnt_tag_square_from_square_as_cropped(self):
        self.given_image_with_data('frost-100x101.jpeg')

        self.image.create_square_representation(32)

        self.assertEqual(self.image.representations.count(), 1)
        rep = self.image.representations.all()[0]
        self.assert_representation(rep, 'image/jpeg', 32, 32, is_cropped=False)

    def test_doesnt_scale_too_small_image(self):
        self.given_image_with_data('frost-100x101.jpeg')

        with patch('subprocess.run') as mock_run:
            self.image.create_square_representation(256)

        self.assertFalse(mock_run.called)

    def test_is_idempotent(self):
        self.given_image_with_data('frost-100x101.jpeg')
        self.image.create_square_representation(32)

        with patch('subprocess.run') as mock_run:
            self.image.create_square_representation(32)

        self.assertFalse(mock_run.called)

    def assert_representation(self, rep, media_type, width, height, is_cropped):
        # Check we have recorded image metadata correctly.
        self.assertEqual(rep.media_type, media_type)
        self.assertEqual(rep.width, width)
        self.assertEqual(rep.height, height)
        if is_cropped:
            self.assertTrue(rep.is_cropped, 'Expected is_cropped')
        else:
            self.assertFalse(rep.is_cropped, 'Expected not is_cropped')

        # Check the content actually maches the metadata.
        with rep.content.open() as f:
            actual_media_type, actual_width, actual_height = _sniff(stdin=f.file)
        self.assertEqual(actual_media_type, media_type)
        self.assertEqual(actual_width, width)
        self.assertEqual(actual_height, height)

    def assert_same_PNG_as_file(self, rep, file_name):
        with open(os.path.join(data_dir, file_name), 'rb') as input:
            expected = input.read()
        with rep.content.open() as f:
            actual = f.read()
        self.asset_same_PNG_data(actual, expected)

    def asset_same_PNG_data(self, a, b, ignore_chunks=None):
        """Check these are essentially the same PNG data.

        Arguments --
            a, b -- bytes objects containing PNG data.
            ignore_chunks -- optional set of chunk types to disregard when comparing.
                By default ignores time and text chunks since they
                vary eacy time PNG is generated.

        This test is still stricter than it should be:
        it expects the same sequence of IDAT chunks,
        instead of smushing them together.
        This will need changing if we want to generate control
        files using a different PNG library from ImageMagick.
        """
        if ignore_chunks is None:
            ignore_chunks = {b'tIME', b'tEXt'}
        chunks_a = [(t, d, c) for t, d, c in _iter_PNG_chunks(a) if t not in ignore_chunks]
        chunks_b = [(t, d, c) for t, d, c in _iter_PNG_chunks(b) if t not in ignore_chunks]
        self.assertEqual(chunks_a, chunks_b)


PNG_SIGNATURE = bytes([137, 80, 78, 71, 13, 10, 26, 10])


def _iter_PNG_chunks(data):
    if data[:8] != PNG_SIGNATURE:
        raise ValueError('Data did not start with PNG signature')
    pos = 8
    while pos < len(data):
        (chunk_size, chunk_type), pos = struct.unpack('!L4s', data[pos:pos + 8]), pos + 8
        chunk_data, pos = data[pos:pos + chunk_size], pos + chunk_size
        chunk_crc, pos = struct.unpack('!L', data[pos:pos + 4]), pos + 4
        yield chunk_type, chunk_data, chunk_crc
    if pos != len(data):
        raise ValueError('Bad chunk(s) in PNG data')


class TestImageFindSquareRepresentation(ImageTestMixin, TestCase):

    def test_returns_exact_match_if_exists(self):
        self.given_image_with_data('im.png')
        rep = self.image.representations.create(width=100, height=100, is_cropped=True)
        self.image.representations.create(width=200, height=200, is_cropped=True)
        self.image.representations.create(width=128, height=77, is_cropped=False)

        result = self.image.find_square_representation(100)

        self.assertEqual(result, rep)

    def test_returns_nearest_smaller_match_and_queues_creation(self):
        self.given_image_with_data('im.png')
        rep = self.image.representations.create(width=100, height=100, is_cropped=True)
        self.image.representations.create(width=200, height=200, is_cropped=True)
        self.image.representations.create(width=128, height=77, is_cropped=False)

        with patch.object(signal_handlers, 'create_image_square_representation') as create_image_square_representation:
            result = self.image.find_square_representation(150)

        self.assertEqual(result, rep)
        create_image_square_representation.delay.assert_called_with(self.image.pk, 150)

    def test_returns_nothing_if_none_suitable(self):
        self.given_image_with_data('im.png')
        self.image.representations.create(width=640, height=384, is_cropped=True)

        with patch.object(signal_handlers, 'create_image_square_representation') as create_image_square_representation:
            result = self.image.find_square_representation(150)

        self.assertFalse(result)
        create_image_square_representation.delay.assert_called_with(self.image.pk, 150)

    def test_queues_retrieval_if_no_cached_data(self):
        self.image = Image.objects.create(data_url='http://example.com/69')  # No data

        with self.settings(IMAGES_FETCH_DATA=True), \
                patch.object(signal_handlers, 'create_image_square_representation') as create_image_square_representation, \
                patch.object(signal_handlers, 'retrieve_image_data') as retrieve_image_data, \
                patch.object(signal_handlers, 'chain') as chain:
            result = self.image.find_square_representation(150)

        self.assertFalse(result)
        chain.assert_called_with(
            retrieve_image_data.s(self.image.pk, if_not_retrieved_since=None),
            create_image_square_representation.si(self.image.pk, 150))
        chain.return_value.delay.assert_called_with()


class TestImageWantsSIze(TestCase):

    def test_queues_retrieve_if_no_cached_data(self):
        image = Image.objects.create(data_url='https://example.com/images/1.jpeg')

        with self.settings(IMAGES_FETCH_DATA=True), \
                patch.object(signal_handlers, 'retrieve_image_data') as retrieve_image_data:
            image.wants_size()

        retrieve_image_data.delay.assert_called_with(image.pk, if_not_retrieved_since=None)
