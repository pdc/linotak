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
import requests
import subprocess

from .signals import wants_data, wants_square_representation


class Image(models.Model):
    """The source data fro an image displayed in a note."""

    MAX_DATA = 10 * 1024 * 1024

    data_url = models.URLField(
        max_length=1000,
        unique=True,
    )
    media_type = models.CharField(
        max_length=200,
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
        return self.data_url.rsplit('/', 1)[-1]

    def retrieve_data(self, if_not_retrieved_since=None, save=False):
        """Download the image data if available."""
        if self.retrieved and (not if_not_retrieved_since or if_not_retrieved_since < self.retrieved):
            return
        r = requests.get(self.data_url)
        buf = io.BytesIO()
        total_size = 0
        hasher = md5()
        for chunk in r.iter_content(chunk_size=10_240):
            total_size += len(chunk)
            buf.write(chunk)
            hasher.update(chunk)
        self.etag = hasher.digest()

        self._sniff(input=buf.getvalue())  # Needed to get file type for file name.
        file_name = file_name_from_etag(self.etag, self.media_type)
        self.cached_data.save(file_name, File(buf), save=save)

    def sniff(self, save=False):
        """Presuming already has image data, guess width, height, and media_type."""
        with self.cached_data.open() as f:
            self._sniff(stdin=f.file)

    def _sniff(self, **kwargs):
        """Given a file-like object, guess width, height, and media_type.

        Arguments --
            kwargs -- how to get the input. Either stdin=REALFILE or input=BYTES
        """
        self.media_type, self.width, self.height = _sniff(**kwargs)

    @transaction.atomic
    def create_square_representation(self, size):
        """Create a representation (probably cropped) of this image."""
        if self.width <= size and self.height <= size:
            # Do not enlarge to fit!
            return
        if self.representations.filter(width=size, height=size).exists():
            return

        cmd = ['convert', '-', '-resize', '^%dx%d>' % (size, size), '-']
        scale = max(size / self.width, size / self.height)
        is_cropped = round(scale * self.width) != round(scale * self.height)
        if is_cropped:
            cmd[-1:-1] = ['-gravity', 'center', '-extent', '%dx%d' % (size, size)]
        with self.cached_data.open() as f:
            output = subprocess.run(cmd, check=True, stdin=f.file, stdout=subprocess.PIPE).stdout
        etag = md5(output).digest()
        with transaction.atomic():
            rep = self.representations.create(media_type=self.media_type, width=size, height=size, is_cropped=is_cropped, etag=etag)
            rep.content.save(file_name_from_etag(rep.etag, rep.media_type), ContentFile(output))

    def find_square_representation(self, size):
        """Return the best match for a square area of this size.

        If there is no exact match, fires signal.
        """
        results = list(self.representations.filter(width__lte=size, height__lte=size).order_by((F('width') * F('height')).desc())[:1])
        result = results[0] if results else None
        if not result or result.width != size or result.height != size:
            wants_square_representation.send(self.__class__, instance=self, size=size)
        return result

    def wants_size(self):
        """Indicates size is wanted and not available."""
        wants_data.send(self.__class__, instance=self)


def _sniff(**kwargs):
    """Given a file-like object, guess media_type, width, and height.

    Arguments --
        kwargs -- how to get the input. Either stdin=REALFILE or input=BYTES

    Returns --
        MEDIA_TYPE, WIDTH, HEIGHT
    """
    cmd = ['identify', '-']
    output = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, **kwargs).stdout
    _, type, size, *rest = output.split()
    w, h = size.split(b'x')
    return media_type_from_imagemagick_type(type), int(w), int(h)


def media_type_from_imagemagick_type(type):
    """Given the type of image as reported by ImageMagick, return MIME type."""
    return 'image/%s' % type.decode('UTF-8').lower()


def suffix_from_media_type(media_type):
    """Given an image MIME type, return file-name suffix."""
    return '.' + media_type.split('/', 1)[1]


def file_name_from_etag(etag, media_type):
    return urlsafe_b64encode(etag).decode('ascii') + suffix_from_media_type(media_type)


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
        max_length=200,
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

