"""Tests for the Images app."""

from base64 import b64encode
from datetime import timedelta
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
import httpretty
import io
import pathlib
import struct
from unittest.mock import patch

from ..matchers_for_mocks import DateTimeTimestampMatcher
from .models import (
    Image, Representation, _sniff, CannotSniff, _sniff_svg,
    suffix_from_media_type, _comb_imagemagick_verbose,
    _lab_from_imagemagick_verbose_bits,
    sRGB_from_Lab
)
from .size_spec import SizeSpec
from .templatetags.image_representations import _image_representation
from . import models, signal_handlers, tasks  # For mocking


# How we obtain real test files:
data_dir = pathlib.Path(__file__).parent / 'test-data'
data_storage = FileSystemStorage(location=data_dir)


class ImageTestMixin:

    image = None

    def tearDown(self):
        if self.image and self.image.cached_data:
            for rep in self.image.representations.all():
                rep.content.delete()
            self.image.cached_data.delete()

    def given_image_with_data(self, file_name, sniffed=True, **kwargs):
        self.data = (data_dir / file_name).read_bytes()
        self.image = Image.objects.create(data_url='http://example.com/69', **kwargs)
        self.image.cached_data.save('test.png', ContentFile(self.data))
        if sniffed:
            self.image.sniff(save=True)

    def with_representation(self, file_name, **kwargs):
        self.data = (data_dir / file_name).read_bytes()
        self.representation = Representation.objects.create(image=self.image, **kwargs)
        self.representation.content.save('r.png', ContentFile(self.data))

    def given_downloadable_image(self, data=None, media_type='image/png', **kwargs):
        self.data = data if data is not None else (data_dir / '234x123.png').read_bytes()
        img_src = 'http://example.com/2'
        self.image = Image.objects.create(data_url=img_src, **kwargs)
        httpretty.register_uri(
            httpretty.GET, img_src,
            body=self.data,
            add_headers={
                'Content-Type': media_type,
            },
        )

    def then_retrieved_and_sniffed(self, media_type='image/png', width=234, height=123):
        self.assertEqual(self.image.media_type.split(';', 1)[0], media_type)
        self.assertEqual(self.image.width, width)
        self.assertEqual(self.image.height, height)
        with self.image.cached_data.open() as f:
            actual = f.read()
        self.assertEqual(actual, self.data)
        self.assertTrue(self.image.retrieved)


class TestImageSniff(ImageTestMixin, TestCase):
    """Test Image.sniff."""

    def test_can_get_width_and_height_of_png(self):
        image = self.create_image_with_data_from_file('234x123.png')

        image.sniff()

        self.assertEqual(image.media_type, 'image/png')
        self.assertEqual(image.width, 234)
        self.assertEqual(image.height, 123)

    def test_can_get_width_and_height_of_jpeg(self):
        image = self.create_image_with_data_from_file('frost-100x101.jpeg')

        image.sniff()

        self.assertEqual(image.media_type, 'image/jpeg')
        self.assertEqual(image.width, 100)
        self.assertEqual(image.height, 101)

    def test_can_determine_placeholder_colour(self):
        image = self.create_image_with_data_from_file('234x123.png')

        image.sniff()

        # Tests for the plucking of the values from the `identify` output in TestExtractStats below.
        # RGB calculated using colormine.com!
        self.assertEqual(image.placeholder, '#D57CD9')

    def test_doesnt_explode_if_not_image(self):
        image = self.create_image_with_data(b'Nope.')

        with self.assertRaises(CannotSniff):
            image.sniff()

        self.assertIsNone(image.media_type)
        self.assertIsNone(image.width)
        self.assertIsNone(image.height)

    def create_image_with_data(self, data):
        """Create image with these bytes"""
        image = Image.objects.create(data_url='https://example.org/1')
        image.cached_data.save('test_file', ContentFile(data), save=True)
        return image

    def create_image_with_data_from_file(self, file_name):
        """Create an image and remember to delete it."""
        self.image = Image.objects.create(data_url='https://example.org/1')
        data = (data_dir / file_name).read_bytes()
        self.image.cached_data.save('test_file', ContentFile(data), save=True)
        # Intentionally don’t give it a ‘.png’ extension.
        return self.image


class TestSniffSVG(TestCase):

    def test_can_get_width_and_height_of_svg_with_width_and_height(self):
        media_type, width, height, _ = _sniff_svg(
            input=b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 6 3" height="600px" width="300px"/>')

        self.assertEqual(media_type, 'image/svg+xml')
        self.assertEqual(width, 300)
        self.assertEqual(height, 600)

    def test_comverts_mm_to_px(self):
        media_type, width, height, _ = _sniff_svg(
            input=(
                b'<svg xmlns="http://www.w3.org/2000/svg" '
                b'viewBox="0 0 713.35878 175.8678" height="49.633801mm" width="201.3257mm"/>'))

        self.assertEqual(media_type, 'image/svg+xml')
        self.assertEqual(width, 761)
        self.assertEqual(height, 188)

    def test_can_get_width_and_height_of_svg_with_view_box(self):
        media_type, width, height, _ = _sniff_svg(
            input=b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 48"/>')

        self.assertEqual(media_type, 'image/svg+xml')
        self.assertEqual(width, 72)
        self.assertEqual(height, 48)

    def test_accepts_unitless_lengths(self):
        media_type, width, height, _ = _sniff_svg(
            input=b'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="270"/>')

        self.assertEqual(media_type, 'image/svg+xml')
        self.assertEqual(width, 640)
        self.assertEqual(height, 270)

    def test_accepts_namespaceless_svg(self):
        media_type, width, height, _ = _sniff_svg(
            input=b'<svg width="640px" height="270px"/>')

        self.assertEqual(media_type, 'image/svg+xml')
        self.assertEqual(width, 640)
        self.assertEqual(height, 270)

    def test_not_confused_by_xml_decl(self):
        media_type, width, height, _ = _sniff_svg(
            input=b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="640px" height="270px"/>')

        self.assertEqual(media_type, 'image/svg+xml')
        self.assertEqual(width, 640)
        self.assertEqual(height, 270)

    def test_rejects_non_svg(self):
        media_type, width, height, _ = _sniff_svg(
            input=b'<html/>')

        self.assertFalse(media_type)


class TestDeleteIfSmall(ImageTestMixin, TestCase):

    def test_deletes_if_small(self):
        self.given_image_with_data('37x57.jpeg')
        self.with_representation('37x57.jpeg', width=37, height=57, is_cropped=False)
        file_names = [self.image.cached_data.name, self.representation.content.name]

        self.image.delete_if_small()

        for n in file_names:
            self.assertFalse((pathlib.Path(settings.MEDIA_ROOT) / n).exists())
        self.assertFalse(Image.objects.filter(pk=self.image.pk).exists())


class TestImageRetrieve(ImageTestMixin, TestCase):
    """Test Image.retrieve."""

    @httpretty.activate(allow_net_connect=False)
    def test_can_retrive_image_and_sniff(self):
        self.given_downloadable_image()

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
        self.given_downloadable_image(retrieved=then)

        self.image.retrieve_data(if_not_retrieved_since=then)

        self.then_retrieved_and_sniffed()

    @httpretty.activate(allow_net_connect=False)
    def test_does_not_retrieve_if_retrieved_later(self):
        then = timezone.now() - timedelta(hours=1)
        earlier = timezone.now() - timedelta(hours=2)
        self.image = Image.objects.create(data_url='https://example.com/1', retrieved=then)

        self.image.retrieve_data(if_not_retrieved_since=earlier)
        # Attempting to download will cause HTTPretty to complain.

    @httpretty.activate(allow_net_connect=False)
    def test_does_not_explode_if_data_isnt_image(self):
        self.given_downloadable_image(b'LOLWAT', media_type='text/plain')

        with patch.object(models, 'logger') as logger:
            self.image.retrieve_data(if_not_retrieved_since=None)

        self.then_retrieved_and_sniffed('text/plain', None, None)
        self.assertTrue(logger.warning.called)

    @httpretty.activate(allow_net_connect=False)
    def test_gets_data_from_data_url(self):
        self.data = (data_dir / 'smol.gif').read_bytes()
        data_url = 'data:image/gif;base64,' + b64encode(self.data).decode('UTF-8')
        self.image = Image.objects.create(data_url=data_url)

        with patch.object(models, 'logger') as logger:
            self.image.retrieve_data(if_not_retrieved_since=None)

        self.then_retrieved_and_sniffed('image/gif', 1020, 100)


class TestSuffixFromMediaType(TestCase):

    def test_returns_jpeg_for_jpeg(self):
        self.assertEqual(suffix_from_media_type('image/jpeg'), '.jpeg')
        self.assertEqual(suffix_from_media_type('image/png'), '.png')
        self.assertEqual(suffix_from_media_type('image/gif'), '.gif')

    def test_returns_svg_for_svg(self):
        self.assertEqual(suffix_from_media_type('image/svg+xml'), '.svg')
        self.assertEqual(suffix_from_media_type('image/svg'), '.svg')

    def test_returns_html_for_html(self):  # Not that that makes any sense for an image …
        self.assertEqual(suffix_from_media_type('text/html'), '.html')
        self.assertEqual(suffix_from_media_type('text/html; charset=UTF-8'), '.html')


class TestRetrieveImageDate(ImageTestMixin, TestCase):

    @httpretty.activate(allow_net_connect=False)
    def test_retrieves_and_sniffs(self):
        self.given_downloadable_image((data_dir / '234x123.png').read_bytes())

        tasks.retrieve_image_data(self.image.pk, None)

        self.image.refresh_from_db()
        self.then_retrieved_and_sniffed()

    @httpretty.activate(allow_net_connect=False)
    def test_retrieves_and_deletes_if_small(self):
        self.given_downloadable_image((data_dir / 'im-32sq.png').read_bytes())

        tasks.retrieve_image_data(self.image.pk, None)

        self.assertFalse(Image.objects.filter(pk=self.image.pk).exists())


class TestSniffImageDataTask(ImageTestMixin, TestCase):

    def test_sniffs_and_saves(self):
        self.given_image_with_data('234x123.png', sniffed=False)

        tasks.sniff_image_data(self.image.pk)

        # Check it has been sniffed and saved, and has not, for example,
        # raised an exception because of a signature change.
        self.image.refresh_from_db()
        self.assertEqual((self.image.width, self.image.height), (234, 123))

    def test_sniffs_and_deletes_if_small(self):
        self.given_image_with_data('im-32sq.png', sniffed=False)

        tasks.sniff_image_data(self.image.pk)

        # Check image has been deleted.
        self.assertFalse(Image.objects.filter(pk=self.image.pk).exists())


class TestSignalHandler(TransactionTestCase):  # Different superclass so that on_commit hooks are called.
    """Test the signal handler."""

    # The retireval of image data is suppressed during testing,
    # so in these tests we need to explictly enable it.

    def test_queues_retrieve_when_image_created(self):
        """Test signal handler queues retrieve when image created."""
        with self.settings(IMAGES_FETCH_DATA=True), patch.object(tasks, 'retrieve_image_data') as retrieve_image_data:
            self.image = Image.objects.create(data_url='https://example.com/1')

        retrieve_image_data.s.assert_called_with(self.image.pk, if_not_retrieved_since=None)
        retrieve_image_data.s.return_value.delay.assert_called_with()  # from on_commit

    def test_doesnt_queue_retrieve_when_retrieved_is_set(self):
        """Test signal handler doesnt queue retrieve when retrieved is set."""
        with self.settings(IMAGES_FETCH_DATA=True), patch.object(tasks, 'retrieve_image_data') as retrieve_image_data:
            self.image = Image.objects.create(data_url='https://example.com/1', retrieved=timezone.now())

        self.assertFalse(retrieve_image_data.s.called)

    def test_doesnt_queue_retrieve_when_size_knwn_to_be_too_small(self):
        """Test signal handler doesnt queue retrieve when retrieved is set."""
        with self.settings(IMAGES_FETCH_DATA=True), patch.object(tasks, 'retrieve_image_data') as retrieve_image_data:
            self.image = Image.objects.create(data_url='https://example.com/1', width=32, height=32)

        self.assertFalse(retrieve_image_data.s.called)


class TestImageQueueRetrieveData(TransactionTestCase):

    def test_sends_timestamp_from_retrieved(self):
        """Test signal handler queues retrieve when image created."""
        image = Image.objects.create(data_url='https://example.com/1', retrieved=timezone.now())

        with self.settings(IMAGES_FETCH_DATA=True), patch.object(tasks, 'retrieve_image_data') as retrieve_image_data:
            image.queue_retrieve_data()

        retrieve_image_data.s.assert_called_with(image.pk, if_not_retrieved_since=DateTimeTimestampMatcher(image.retrieved))
        retrieve_image_data.s.return_value.delay.assert_called_with()  # from on_commit


class TestImageCreateSquareRepresentation(ImageTestMixin, TestCase):

    def test_can_create_square_from_rect(self):
        self.given_image_with_data('im.png')

        self.image.create_square_representation(32)

        # convert - -resize '^32x32>' -gravity center -extent 32x32 - < linotak/images/test-data/im.png > linotak/images/test-data/im-32sq.png
        self.assertEqual(self.image.representations.count(), 1)
        rep = self.image.representations.all()[0]
        self.assert_representation(rep, 'image/png', 32, 32, is_cropped=True)
        self.assert_same_PNG_as_file(rep, 'im-32sq.png')

    def test_offsets_crop_to_suit_focus(self):
        self.given_image_with_data('im.png', focus_x=0.333, focus_y=0.75)

        self.image.create_square_representation(32)

        # convert - -resize '^32x32>' -extent 32x32+7+0 - < linotak/images/test-data/im.png > linotak/images/test-data/im-32sq2.png
        # The +7 comes from (52.6 - 32) * 0.333.
        self.assertEqual(self.image.representations.count(), 1)
        rep = self.image.representations.all()[0]
        self.assert_representation(rep, 'image/png', 32, 32, is_cropped=True)
        self.assert_same_PNG_as_file(rep, 'im-32sq2.png')

    def test_doesnt_tag_square_from_square_as_cropped(self):
        self.given_image_with_data('frost-100x101.jpeg')

        self.image.create_square_representation(32)

        self.assertEqual(self.image.representations.count(), 1)
        rep = self.image.representations.all()[0]
        self.assert_representation(rep, 'image/jpeg', 32, 32, is_cropped=False)

    def test_doesnt_scale_too_small_image(self):
        self.given_image_with_data('frost-100x101.jpeg')

        self.image.create_square_representation(256)

        # It does create a representation, but it is the original image data (unscaled).
        self.assertEqual(self.image.representations.count(), 1)
        rep = self.image.representations.all()[0]
        self.assert_representation(rep, 'image/jpeg', 100, 101, is_cropped=False)
        self.assert_same_data_as_file(rep, 'frost-100x101.jpeg')

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
            actual_media_type, actual_width, actual_height, _ = _sniff(stdin=f.file)
        self.assertEqual(actual_media_type, media_type)
        self.assertEqual(actual_width, width)
        self.assertEqual(actual_height, height)

    def assert_same_data_as_file(self, rep, file_name):
        expected = (data_dir / file_name).read_bytes()
        with rep.content.open() as f:
            actual = f.read()
        self.assertEqual(actual, expected, 'expected content of %s to match %s' % (rep, file_name))

    def assert_same_PNG_as_file(self, rep, file_name):
        expected = (data_dir / file_name).read_bytes()
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


class TestSizeSpec(TestCase):

    def test_can_parse_widthxheight(self):
        result = SizeSpec.parse('600x500')

        self.assertEqual(result.width, 600)
        self.assertEqual(result.height, 500)

    def test_can_parse_min_ratio(self):
        result = SizeSpec.parse('600x500 min 2:1')

        self.assertEqual(result.width, 600)
        self.assertEqual(result.height, 500)
        self.assertEqual(result.min_ratio, (2, 1))

    def test_can_parse_min_max_ratio(self):
        result = SizeSpec.parse('550x500 min 3:4 max 6:5')

        self.assertEqual(result.width, 550)
        self.assertEqual(result.height, 500)
        self.assertEqual(result.min_ratio, (3, 4))
        self.assertEqual(result.max_ratio, (6, 5))

    def test_can_write_spec(self):
        result = SizeSpec(1280, 768).unparse()

        self.assertEqual(result, '1280x768')

    def test_can_write_spec_with_min_max(self):
        result = SizeSpec(1280, 768, (2, 3), (4, 5)).unparse()

        self.assertEqual(result, '1280x768 min 2:3 max 4:5')

    def test_scales_down_to_fit_box(self):
        self.assertEqual(
            SizeSpec(640, 480).scale_and_crop_to_match(1000, 2000),
            ((240, 480), None))
        self.assertEqual(
            SizeSpec(640, 480).scale_and_crop_to_match(2000, 1000),
            ((640, 320), None))
        self.assertEqual(
            SizeSpec(640, 320).scale_and_crop_to_match(2000, 1000),
            ((640, 320), None))
        self.assertEqual(
            SizeSpec(640, 480).scale_and_crop_to_match(2000, 2000),
            ((480, 480), None))
        self.assertEqual(
            SizeSpec(640, 360).scale_and_crop_to_match(4000, 3000),
            ((480, 360), None))

    def test_crops_to_make_not_as_tall(self):
        self.assertEqual(
            SizeSpec(640, 480, min_ratio=(3, 4)).scale_and_crop_to_match(1000, 2000),
            ((360, 720), (360, 480)))

    def test_crops_to_make_not_as_wide(self):
        self.assertEqual(
            SizeSpec(640, 480, max_ratio=(3, 2)).scale_and_crop_to_match(2000, 1000),
            ((853, 427), (640, 427)))

    def test_rounds_to_nearest_int(self):
        self.assertEqual(
            SizeSpec(480, 320).scale_and_crop_to_match(3500, 2400),
            ((467, 320), None))
        self.assertEqual(
            SizeSpec(320, 480).scale_and_crop_to_match(2400, 3500),
            ((320, 467), None))

    def test_does_not_scale_up(self):
        self.assertEqual(
            SizeSpec(1600, 900).scale_and_crop_to_match(600, 500),
            ((600, 500), None))

    def test_can_make_squares(self):
        self.assertEqual(
            SizeSpec(600, 600, min_ratio=(1, 1), max_ratio=(1, 1)).scale_and_crop_to_match(3000, 2000),
            ((900, 600), (600, 600)))


class TestImageFindSquareRepresentation(ImageTestMixin, TestCase):

    def setUp(self):
        """Create image with data and a reasonably large soure size."""
        self.image = Image.objects.create(data_url='im.png', width=1280, height=768)
        self.image.cached_data.save('foo.png', ContentFile(b'LOLWAT'))

    def test_returns_exact_match_if_exists(self):
        rep = self.image.representations.create(width=100, height=100, is_cropped=True)
        self.image.representations.create(width=200, height=200, is_cropped=True)
        self.image.representations.create(width=128, height=77, is_cropped=False)

        result = self.image.find_square_representation(100)

        self.assertEqual(result, rep)

    def test_returns_nearest_smaller_match_and_queues_creation(self):
        rep = self.image.representations.create(width=100, height=100, is_cropped=True)
        self.image.representations.create(width=200, height=200, is_cropped=True)
        self.image.representations.create(width=128, height=77, is_cropped=False)

        with patch.object(self.image, 'queue_representation') as queue_representation:
            result = self.image.find_square_representation(150)

        self.assertEqual(result, rep)
        queue_representation.assert_called_with(SizeSpec.of_square(150))

    def test_returns_nothing_if_none_suitable(self):
        self.image.representations.create(width=640, height=384, is_cropped=True)

        with patch.object(self.image, 'queue_representation') as queue_representation:
            result = self.image.find_square_representation(150)

        self.assertFalse(result)
        queue_representation.assert_called_with(SizeSpec.of_square(150))

    def test_queues_retrieval_if_no_cached_data(self):
        self.image = Image.objects.create(data_url='http://example.com/69')  # No data

        with self.settings(IMAGES_FETCH_DATA=True), \
                patch.object(tasks, 'create_image_representation') as create_image_representation, \
                patch.object(tasks, 'retrieve_image_data') as retrieve_image_data, \
                patch.object(signal_handlers, 'chain') as chain:
            result = self.image.find_square_representation(150)

        self.assertFalse(result)
        chain.assert_called_with(
            retrieve_image_data.s(self.image.pk, if_not_retrieved_since=None),
            create_image_representation.si(self.image.pk, SizeSpec.of_square(150).unparse()))
        chain.return_value.delay.assert_called_with()


class TestImageWantsSize(TestCase):

    def test_queues_retrieve_if_no_cached_data(self):
        image = Image.objects.create(data_url='https://example.com/images/1.jpeg')

        with self.settings(IMAGES_FETCH_DATA=True), \
                patch.object(image, 'queue_retrieve_data') as queue_retrieve_data:
            image.wants_size()

        queue_retrieve_data.assert_called_with()


class TestImageRepresentationTag(TestCase):

    maxDiff = None

    def test_given_svg_generates_svg(self):
        image = Image.objects.create(data_url='http://example.com/foo.svg', media_type='image/svg+xml')
        size_spec = SizeSpec(1000, 500)

        result = _image_representation(image, size_spec)

        self.assertEqual(
            result,
            '<svg width="1000px" height="500px" viewBox="0 0 1000 500">'
            '<image width="1000" height="500" xlink:href="http://example.com/foo.svg"/>'
            '</svg>')

    def test_skrinks_to_fit_svg_if_size_known(self):
        image = Image.objects.create(data_url='http://example.com/foo.svg', media_type='image/svg+xml', width=600, height=400)
        size_spec = SizeSpec(300, 300)

        result = _image_representation(image, size_spec)

        self.assertEqual(
            result,
            '<svg width="300px" height="200px" viewBox="0 0 300 200">'
            '<image width="300" height="200" xlink:href="http://example.com/foo.svg"/>'
            '</svg>')

    def test_scales_up_svg(self):
        image = Image.objects.create(data_url='http://example.com/foo.svg', media_type='image/svg+xml', width=600, height=400)
        size_spec = SizeSpec(900, 900)

        result = _image_representation(image, size_spec)

        self.assertEqual(
            result,
            '<svg width="900px" height="600px" viewBox="0 0 900 600">'
            '<image width="900" height="600" xlink:href="http://example.com/foo.svg"/>'
            '</svg>')

    def test_slices_if_cropped(self):
        image = Image.objects.create(data_url='http://example.com/foo.svg', media_type='image/svg+xml', width=600, height=400)
        size_spec = SizeSpec.of_square(600)

        result = _image_representation(image, size_spec)

        self.assertEqual(
            result,
            '<svg width="600px" height="600px" viewBox="0 0 900 600" preserveAspectRatio="xMidYMid slice">'
            '<image width="900" height="600" xlink:href="http://example.com/foo.svg"/>'
            '</svg>')


# identify -colorspace Lab -verbose linotak/images/test-data/234x123.png
sample_verbose = """Image: linotak/images/test-data/234x123.png
  Format: PNG (Portable Network Graphics)
  Mime type: image/png
  Class: DirectClass
  Geometry: 234x123+0+0
  Resolution: 72x72
  Print size: 3.25x1.70833
  Units: PixelsPerCentimeter
  Colorspace: CIELab
  Type: Palette
  Base type: Undefined
  Endianess: Undefined
  Depth: 8/16-bit
  Channel depth:
    Channel 0: 16-bit
    Channel 1: 16-bit
    Channel 2: 16-bit
  Channel statistics:
    Pixels: 28782
    Channel 0:
      min: 100.242  (0.393107)
      max: 184.861 (0.724945)
      mean: 164.582 (0.64542)
      standard deviation: 35.6815 (0.139928)
      kurtosis: -0.493308
      skewness: -1.21686
      entropy: 0.146701
    Channel 1:
      min: 156.365  (0.613196)
      max: 181.555 (0.711982)
      mean: 176.387 (0.691714)
      standard deviation: 8.70216 (0.0341261)
      kurtosis: -0.552761
      skewness: -1.19121
      entropy: 0.147456
    Channel 2:
      min: 53.3958  (0.209395)
      max: 107.279 (0.420703)
      mean: 94.3706 (0.370081)
      standard deviation: 22.7183 (0.0890913)
      kurtosis: -0.491737
      skewness: -1.21749
      entropy: 0.146701
  """


class TestExtractStats(TestCase):

    def test_extracts_stats_by_path(self):
        spec = [
            ['Channel statistics', 'Channel 0', 'mean'],
            ['Channel statistics', 'Channel 1', 'mean'],
            ['Channel statistics', 'Channel 2', 'mean'],
        ]

        result = _comb_imagemagick_verbose(spec, io.StringIO(sample_verbose))

        self.assertEqual(result, ('164.582 (0.64542)', '176.387 (0.691714)', '94.3706 (0.370081)'))

    def test_extracts_Lab_from_verbose_bits(self):
        l_star, a_star, b_star = _lab_from_imagemagick_verbose_bits(
            ('164.582 (0.64542)', '176.387 (0.691714)', '94.3706 (0.370081)')
        )

        self.assertAlmostEqual(l_star, 64.542, 3)
        self.assertAlmostEqual(a_star, 48.387, 3)
        self.assertAlmostEqual(b_star, -33.629, 3)

    def test_Lab_from_bits_white(self):
        l_star, a_star, b_star = _lab_from_imagemagick_verbose_bits(('0 (0)', '127.5 (0.5)', '127.5 (0.5)'))

        self.assertAlmostEqual(l_star, 0.0, 3)

    def test_Lab_from_bits_black(self):
        l_star, a_star, b_star = _lab_from_imagemagick_verbose_bits(('255 (1)', '127.5 (0.5)', '127.5 (0.5)'))

        self.assertAlmostEqual(l_star, 100.0, 3)

    def test_sRGB_from_Lab(self):
        r, g, b = sRGB_from_Lab((64.542, 48.38707000000002, -33.62934))

        # Calculated using colormine.org
        self.assertAlmostEqual(r, 213, 3)
        self.assertAlmostEqual(g, 124, 3)
        self.assertAlmostEqual(b, 217, 3)
