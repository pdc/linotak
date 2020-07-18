"""Modles for images.

Images have two main classes:

    Image: the source data for an image.
        In RDF terms, this is the resource.
    Representation: information about where we stored a
        scaled version of an image
"""

from base64 import b64decode, urlsafe_b64encode
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from hashlib import md5
import io
import logging
import re
import requests
import subprocess
from xml.etree import ElementTree

from .signals import wants_data, wants_representation
from .size_spec import SizeSpec


logger = logging.getLogger(__name__)

MAX_LENGTH = 4000


class CannotSniff(Exception):
    """Raised if cannot sniff. Args are returncode & message from ImageMagick."""

    def __str__(self):
        returncode, message = self.args
        return 'ImageMagick identify returned status %d: %r' % (returncode, message)


class Image(models.Model):
    """The source data for an image displayed in a note."""

    class NotSniffable(CannotSniff):
        """Raised if cannot sniff. Args are file_name and returncode & message from ImageMagick."""

        def __str__(self):
            file_name, returncode, message = self.args
            return 'Could not identify %s: ImageMagick identify returned status %d: %r' % (file_name, returncode, message)

    MAX_DATA = 10 * 1024 * 1024
    MIN_WIDTH = MIN_HEIGHT = 80

    data_url = models.URLField(
        _('data URL'),
        max_length=MAX_LENGTH,
        unique=True,
    )
    media_type = models.CharField(
        _('media-type'),
        max_length=MAX_LENGTH,
        validators=[
            RegexValidator(r'^(image|application)/[\w.+-]+(;\s*\w+=.*)?$'),
        ],
        null=True,
        blank=True,
        help_text=_('MIME media-type for this image source, such as image/jpeg'),
    )
    cached_data = models.FileField(
        _('cached data'),
        upload_to='cached-images',
        null=True,
        blank=True,
        help_text=_('A copy of the image data from which we can generate scaled representations.'),
    )
    width = models.PositiveIntegerField(
        _('width'),
        null=True,
        blank=True,
    )
    height = models.PositiveIntegerField(
        _('height'),
        null=True,
        blank=True,
    )
    etag = models.BinaryField(
        _('etag'),
        max_length=16,
        null=True,
        blank=True,
        editable=False,
        help_text='Hash of the image data when retrieved.',
    )
    retrieved = models.DateTimeField(
        _('retrieved'),
        null=True,
        blank=True,
    )

    created = models.DateTimeField(_('created'), default=timezone.now)
    modified = models.DateTimeField(_('modified'), auto_now=True)

    class Meta:
        verbose_name = _('image')
        verbose_name_plural = _('images')

    def __str__(self):
        last_part = self.data_url.rsplit('/', 1)[-1]
        if len(last_part) > 60:
            return '%s…%s' % (last_part[:30], last_part[-20:])
        return last_part

    def retrieve_data_task(self):
        """Celery signature to arrange for async download of this image."""
        from . import tasks

        return tasks.retrieve_image_data.s(self.pk, if_not_retrieved_since=(self.retrieved.timestamp() if self.retrieved else None))

    def queue_retrieve_data(self):
        """Arrange for async download of this image."""
        # Queue after transaction committed to avoid a race with the Celery queue.
        transaction.on_commit(self.retrieve_data_task().delay)

    @transaction.atomic
    def retrieve_data(self, if_not_retrieved_since=None, save=False):
        """Download the image data if available."""
        if self.retrieved and (not if_not_retrieved_since or if_not_retrieved_since < self.retrieved):
            return
        self.retrieved = timezone.now()
        self.save()  # This will be rolled back in case of error but setting it now avoids some race conditons.

        if self.data_url.startswith('data:'):
            media_type, rest = self.data_url.split(';', 1)
            if rest.startswith('base64,'):
                data = b64decode(rest[7:])
            self.etag = md5(data).digest()
            file = ContentFile(data)
        else:
            r = requests.get(self.data_url)
            media_type = r.headers['Content-Type']
            buf = io.BytesIO()
            total_size = 0
            hasher = md5()
            for chunk in r.iter_content(chunk_size=10_240):
                total_size += len(chunk)
                buf.write(chunk)
                hasher.update(chunk)
            self.etag = hasher.digest()
            data = buf.getvalue()
            file = File(buf)

        if media_type:
            self.media_type = media_type
        try:
            self._sniff(input=data, media_type=media_type)  # Needed to get file type for file name.
            file_name = file_name_from_etag(self.etag, self.media_type)
        except Image.NotSniffable as e:
            file_name = file_name_from_etag(self.etag, None)
            logger.warning(e)
        self.cached_data.save(file_name, file, save=save)

    def sniff(self, save=False):
        """Presuming already has image data, guess width, height, and media_type."""
        with self.cached_data.open() as f:
            if not self.etag:
                # Happens if cached data is set outside of retrieve_data.
                hasher = md5()
                chunk = f.read(10_240)
                while chunk:
                    hasher.update(chunk)
                    chunk = f.read(10_240)
                self.etag = hasher.digest()
                f.seek(0)
            self._sniff(stdin=f.file)

    def _sniff(self, media_type=None, **kwargs):
        """Given a file-like object, guess width, height, and media_type.

        Arguments --
            kwargs -- how to get the input. Either stdin=REALFILE or input=BYTES
        """
        try:
            self.media_type, self.width, self.height = _sniff(media_type=media_type, **kwargs)
        except CannotSniff as e:
            rc, msg = e.args
            raise Image.NotSniffable(file_name_from_etag(self.etag, None), rc, msg)

    def delete_if_small(self):
        """If this image is small, delete it."""
        if self.width and self.width < self.MIN_WIDTH and self.height and self.height < self.MIN_HEIGHT:
            for r in self.representations.all():
                r.content.delete(save=False)
                r.delete()
            if self.cached_data:
                self.cached_data.delete(save=False)
            self.delete()

    def create_square_representation(self, size):
        """Create a representation (probably cropped) of this image."""
        return self.create_representation(SizeSpec.of_square(size))

    @transaction.atomic
    def create_representation(self, spec):
        """Create a representation  of this image.

        Arguments --
            spec -- SizeSpec instance that specifies how to scale and crop
        """
        if not self.width or not self.height:
            # Image size not known, so probably not actually an image.
            return None

        scaled, crop = spec.scale_and_crop_to_match(self.width, self.height)
        final_width, final_height = crop or scaled
        if (candidates := self.representations.filter(width=final_width, height=final_height)[:1]):
            # Already done!
            return candidates[0]

        if final_width == self.width and final_height == self.height:
            # Want the original size of the image. Just copy the data directly.
            rep = self.representations.create(media_type=self.media_type, width=self.width, height=self.height, is_cropped=bool(crop), etag=self.etag)
            with self.cached_data.open() as f:
                rep.content.save(file_name_from_etag(rep.etag, rep.media_type), f)
            return

        if crop:
            cmd = ['convert', '-', '-resize', '^%dx%d>' % scaled, '-gravity', 'center', '-extent', '%dx%d' % crop, '-']
        else:
            cmd = ['convert', '-', '-resize', '%dx%d>' % scaled, '-']
        with self.cached_data.open() as f:
            output = subprocess.run(cmd, check=True, stdin=f.file, stdout=subprocess.PIPE).stdout
        etag = md5(output).digest()
        output_file = ContentFile(output)
        rep = self.representations.create(media_type=self.media_type, width=final_width, height=final_height, is_cropped=bool(crop), etag=etag)
        rep.content.save(file_name_from_etag(rep.etag, rep.media_type), output_file)
        return rep

    def representation_task(self, spec):
        """Celery signature to arrange for representarion to be created.

        Do not try to do this in the same transaction as creates the image,
        as this causes a race condition.
        """
        from . import tasks

        return tasks.create_image_representation.si(self.pk, spec.unparse())

    def queue_representation(self, spec):
        """Arrange for representation satisfying this spec to be created.

        Do not try to do this in the same transaction as creates the image,
        as this causes a race condition.
        """
        self.representation_task(spec).delay()

    @transaction.atomic
    def find_representation(self, spec):
        """Return the best match for an area of this size.

        If there is no exact match, fires signal.
        """
        if self.width and self.height:
            final_width, final_height = spec.best_match(self.width, self.height)
            results = list(
                self.representations
                .filter(width__lte=final_width, height__lte=final_height)
                .order_by((F('width') * F('height')).desc())
                [:1]
            )
            result = results[0] if results else None
        else:
            result = None
        if not result or result.width != final_width or result.height != final_height:
            wants_representation.send(self.__class__, instance=self, spec=spec)
        return result

    def find_square_representation(self, size):
        """Return the best match for a square area of this size.

        If there is no exact match, fires signal.
        """
        return self.find_representation(SizeSpec.of_square(size))

    def wants_size(self):
        """Indicates size is wanted and not available."""
        if self.width and self.height:
            return
        wants_data.send(self.__class__, instance=self)


def _sniff(media_type=None, **kwargs):
    """Given a file-like object, guess media_type, width, and height.

    Arguments --
        kwargs -- how to get the input. Either stdin=REALFILE or input=BYTES

    Returns --
        MEDIA_TYPE, WIDTH, HEIGHT

    Raises --
        CannotSniff when cannot sniff
    """
    if media_type and 'svg' in media_type:
        media_type_1, width, height = _sniff_svg(**kwargs)
        if media_type_1:
            return media_type_1, width, height
    cmd = ['identify', '-']
    result = subprocess.run(cmd, check=False, stderr=subprocess.PIPE, stdout=subprocess.PIPE, **kwargs)
    if result.returncode:
        # Command failed.
        raise CannotSniff(result.returncode, result.stderr or result.stdout)
    output = result.stdout
    _, type, size, *rest = output.split()
    w, h = size.split(b'x')
    return media_type_from_imagemagick_type(type), int(w), int(h)


_length_pattern = re.compile(r'^\s*(\d+|\d*\.\d+)\s*([a-z]{2,3})?\s*$')
_px_per_unit = {
    'px': 1.0,
    'pt': 96.0 / 72.0,
    'cm': 96.0 / 2.54,
    'mm': 96.0 / 25.4,
    'em': 16.0,  # Assume my usual 16px tyoe size
    'rem': 16.0,  # Ditto
}


def px_from_length(length):
    m = _length_pattern.match(length)
    if m:
        if m[2]:
            return round(float(m[1]) * _px_per_unit[m[2]])
        return round(float(m[1]))


def _sniff_svg(input=None, stdin=None):
    """Given file data that might well be SVG, return type and dimensions.

    Arguments --
        input (bytes instance) -- the image data
        stdin (file-like object) -- contains the image data

    Exactly one of the above should be specified.

    Returns --
        MEDIA_TYPE, WIDTH, HEIGHT
    """
    root = ElementTree.parse(stdin) if stdin else ElementTree.fromstring(input)
    width, height, view_box = root.get('width'), root.get('height'), root.get('viewBox')
    if width and height:
        width, height = px_from_length(width), px_from_length(height)
    elif view_box:
        width, height = view_box.split()[-2:]
        width, height = round(float(width)), round(float(height))
    else:
        width, height = None, None
    return 'image/svg+xml' if root.tag in ['{http://www.w3.org/2000/svg}svg', 'svg'] else None, width, height


_media_types_by_imagemagick = {
    b'SVG': 'image/svg+xml',
}


def media_type_from_imagemagick_type(type):
    """Given the type of image as reported by ImageMagick, return MIME type."""
    return _media_types_by_imagemagick.get(type) or 'image/%s' % type.decode('UTF-8').lower()


_suffixes_by_media = {
    'image/svg+xml': '.svg',
}


def suffix_from_media_type(media_type):
    """Given an image MIME type, return file-name suffix."""
    if not media_type:
        return '.data'
    media_type = media_type.split(';', 1)[0]
    return (_suffixes_by_media.get(media_type) or '.' + media_type.split('/', 1)[1])


def file_name_from_etag(etag, media_type):
    return urlsafe_b64encode(etag).decode('ascii').rstrip('=') + suffix_from_media_type(media_type)


class Representation(models.Model):
    """A representation of an image at a given size."""

    image = models.ForeignKey(
        Image,
        models.CASCADE,
        verbose_name='representation',
        related_name='representations',
        related_query_name='representation',
    )

    content = models.FileField(
        _('content'),
        upload_to='i',
        null=True,
        blank=True,
        help_text=_('Content of the image representation.'),
    )
    media_type = models.CharField(
        _('media-type'),
        max_length=MAX_LENGTH,
        validators=[
            RegexValidator(r'^(image|application)/\w+(;\s*\w+=.*)?$'),
        ],
    )
    width = models.PositiveIntegerField(_('width'))
    height = models.PositiveIntegerField(_('height'))
    is_cropped = models.BooleanField(_('is cropped'))
    etag = models.BinaryField(
        _('etag'),
        max_length=16,
        editable=False,
        help_text=_('Hash of the image data when generated.'),
    )

    created = models.DateTimeField(_('created'), default=timezone.now)
    modified = models.DateTimeField(_('modified'), auto_now=True)

    class Meta:
        verbose_name = 'representation'
        verbose_name_plural = 'representations'
        unique_together = [
            ('image', 'width', 'is_cropped'),
        ]

    def __str__(self):
        return '%s (%dx%d)' % (self.image, self.width, self.height)
