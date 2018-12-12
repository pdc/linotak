"""Modles for images.

Images have two main classes:

    Image: the source data for an image
    Representation: information about where we stored a
        scaled version of an image
"""

from base64 import urlsafe_b64encode
from django.core.files import File
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from hashlib import md5
import io
import requests
import subprocess


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
        return self.data_url

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
        buf.seek(0)
        self.cached_data.save(urlsafe_b64encode(hasher.digest()).decode('ascii'), File(buf))
        self.sniff(save=save)

    def sniff(self, save=False):
        """Presuming already has image data, guess width, height, and media_type."""
        with self.cached_data.open() as f:
            cmd = ['identify', '-']
            output = subprocess.run(cmd, check=True, stdin=f.file, stdout=subprocess.PIPE).stdout
        _, type, size, *rest = output.split()
        self.media_type = 'image/%s' % type.decode('UTF-8').lower()
        w, h = size.split(b'x')
        self.width = int(w)
        self.height = int(h)
        if save:
            self.save()
