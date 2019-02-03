"""Modles for images.

Images have two main classes:

    Image: the source data for an image
    Representation: information about where we stored a
        scaled version of an image
"""

from base64 import urlsafe_b64encode
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone
from hashlib import md5
import io
import logging
import requests
import subprocess

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
    """The source data fro an image displayed in a note."""

    class NotSniffable(CannotSniff):
        """Raised if cannot sniff. Args are file_name and returncode & message from ImageMagick."""

        def __str__(self):
            file_name, returncode, message = self.args
            return 'Could not identify %s: ImageMagick identify returned status %d: %r' % (file_name, returncode, message)

    MAX_DATA = 10 * 1024 * 1024

    data_url = models.URLField(
        max_length=MAX_LENGTH,
        unique=True,
    )
    media_type = models.CharField(
        max_length=MAX_LENGTH,
        validators=[
            RegexValidator(r'^(image|application)/\w+(;\s*\w+=.*)?$'),
        ],
        null=True,
        blank=True,
    )
    cached_data = models.FileField(
        upload_to='cached-images',
        null=True,
        blank=True,
        help_text='A copy of the image data from which we can generate scaled representations.',
    )
    width = models.PositiveIntegerField(
        null=True,
        blank=True,
    )
    height = models.PositiveIntegerField(
        null=True,
        blank=True,
    )
    etag = models.BinaryField(
        max_length=16,
        null=True,
        blank=True,
        editable=False,
        help_text='Hash of the image data when retrieved.',
    )
    retrieved = models.DateTimeField(
        null=True,
        blank=True,
    )

    created = models.DateTimeField(default=timezone.now)
    modified = models.DateTimeField(auto_now=True)

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
        self.save()  # This will be rolled back in case of error but settingit now avoids some race conditons.

        r = requests.get(self.data_url)
        media_type = r.headers['Content-Type']
        if media_type:
            self.media_type = media_type
        buf = io.BytesIO()
        total_size = 0
        hasher = md5()
        for chunk in r.iter_content(chunk_size=10_240):
            total_size += len(chunk)
            buf.write(chunk)
            hasher.update(chunk)
        self.etag = hasher.digest()

        try:
            self._sniff(input=buf.getvalue())  # Needed to get file type for file name.
            file_name = file_name_from_etag(self.etag, self.media_type)
        except Image.NotSniffable as e:
            file_name = file_name_from_etag(self.etag, None)
            logger.warning(e)
        self.cached_data.save(file_name, File(buf), save=save)

    def sniff(self, save=False):
        """Presuming already has image data, guess width, height, and media_type."""
        with self.cached_data.open() as f:
            if not self.etag:
                # GHappens if cached data is set outside of retrieve_data.
                hasher = md5()
                chunk = f.read(10_240)
                while chunk:
                    hasher.update(chunk)
                    chunk = f.read(10_240)
                self.etag = hasher.digest()
                f.seek(0)
            self._sniff(stdin=f.file)

    def _sniff(self, **kwargs):
        """Given a file-like object, guess width, height, and media_type.

        Arguments --
            kwargs -- how to get the input. Either stdin=REALFILE or input=BYTES
        """
        try:
            self.media_type, self.width, self.height = _sniff(**kwargs)
        except CannotSniff as e:
            rc, msg = e.args
            raise Image.NotSniffable(file_name_from_etag(self.etag, None), rc, msg)

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
            return

        scaled, crop = spec.scale_and_crop_to_match(self.width, self.height)
        final_width, final_height = crop or scaled
        if self.representations.filter(width=final_width, height=final_height).exists():
            # Already done!
            return

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
        """Return the best match for a square area of this size.

        If there is no exact match, fires signal.
        """
        if self.width and self.height:
            final_width, final_height = spec.best_match(self.width, self.height)
            results = list(self.representations.filter(width__lte=final_width, height__lte=final_height).order_by((F('width') * F('height')).desc())[:1])
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


def _sniff(**kwargs):
    """Given a file-like object, guess media_type, width, and height.

    Arguments --
        kwargs -- how to get the input. Either stdin=REALFILE or input=BYTES

    Returns --
        MEDIA_TYPE, WIDTH, HEIGHT

    Throws --
        CannotSniff when cannot sniff
    """
    cmd = ['identify', '-']
    result = subprocess.run(cmd, check=False, stderr=subprocess.PIPE, stdout=subprocess.PIPE, **kwargs)
    if result.returncode:
        # Command failed.
        raise CannotSniff(result.returncode, result.stderr or result.stdout)
    output = result.stdout
    _, type, size, *rest = output.split()
    w, h = size.split(b'x')
    return media_type_from_imagemagick_type(type), int(w), int(h)


def media_type_from_imagemagick_type(type):
    """Given the type of image as reported by ImageMagick, return MIME type."""
    return 'image/%s' % type.decode('UTF-8').lower()


def suffix_from_media_type(media_type):
    """Given an image MIME type, return file-name suffix."""
    return '.' + media_type.split('/', 1)[1] if media_type else '.data'


def file_name_from_etag(etag, media_type):
    return urlsafe_b64encode(etag).decode('ascii').rstrip('=') + suffix_from_media_type(media_type)


class Representation(models.Model):
    """A representation of an image at a given size."""

    image = models.ForeignKey(
        Image,
        models.CASCADE,
        related_name='representations',
        related_query_name='representation',
    )

    content = models.FileField(
        upload_to='i',
        null=True,
        blank=True,
        help_text='Content of the image representation.',
    )
    media_type = models.CharField(
        max_length=MAX_LENGTH,
        validators=[
            RegexValidator(r'^(image|application)/\w+(;\s*\w+=.*)?$'),
        ],
    )
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    is_cropped = models.BooleanField()
    etag = models.BinaryField(
        max_length=16,
        editable=False,
        help_text='Hash of the image data when generated.',
    )

    created = models.DateTimeField(default=timezone.now)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [
            ('image', 'width', 'is_cropped'),
        ]

    def __str__(self):
        return '%s (%dx%d)' % (self.image, self.width, self.height)

