"""Modles for images.

Images have two main classes:

    Image: the source data for an image.
        In RDF terms, this is the resource.
        It is augmented with hints for representing it as a thumbnail:
            crop_{left,top,width,height} and focus_[xy]
    Representation: information about where we stored a
        cropped, scaled version of an image
"""

from base64 import b64decode, urlsafe_b64encode
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.validators import RegexValidator, MaxValueValidator, MinValueValidator
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
        return "ImageMagick identify returned status %d: %r" % (returncode, message)


class Image(models.Model):
    """The source data for an image displayed in a note."""

    class NotSniffable(CannotSniff):
        """Raised if cannot sniff. Args are file_name and returncode & message from ImageMagick."""

        def __str__(self):
            file_name, returncode, message = self.args
            return (
                "Could not identify %s: ImageMagick identify returned status %d: %r"
                % (file_name, returncode, message)
            )

    MAX_DATA = 10 * 1024 * 1024
    MIN_WIDTH = MIN_HEIGHT = 80

    data_url = models.URLField(
        _("data URL"),
        max_length=MAX_LENGTH,
        unique=True,
    )
    media_type = models.CharField(
        _("media-type"),
        max_length=MAX_LENGTH,
        validators=[
            RegexValidator(r"^(image|application)/[\w.+-]+(;\s*\w+=.*)?$"),
        ],
        null=True,
        blank=True,
        help_text=_("MIME media-type for this image source, such as image/jpeg"),
    )
    cached_data = models.FileField(
        _("cached data"),
        upload_to="cached-images",
        null=True,
        blank=True,
        help_text=_("A copy of the image data"),
    )
    width = models.PositiveIntegerField(
        _("width"),
        null=True,
        blank=True,
    )
    height = models.PositiveIntegerField(
        _("height"),
        null=True,
        blank=True,
    )
    crop_left = models.FloatField(
        _("crop left"),
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text=_("Range 0.0 to 1.0. Fraction of the way from the left edge"),
    )
    crop_top = models.FloatField(
        _("crop top"),
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text=_("Range 0.0 to 1.0. Fraction of the way down from the top"),
    )
    crop_width = models.FloatField(
        _("crop width"),
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text=_("Range 0.0 to 1.0. Fraction of the way from left toward right"),
    )
    crop_height = models.FloatField(
        _("crop height"),
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text=_("Range 0.0 to 1.0. Fraction of the way from top toward bottom"),
    )
    focus_x = models.FloatField(
        _("focus x"),
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text=_("Range 0.0 to 1.0. Fraction of the way from the left edge"),
    )
    focus_y = models.FloatField(
        _("focus y"),
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text=_("Range 0.0 to 1.0. Fraction of the way down from the top"),
    )
    placeholder = models.CharField(
        _("placeholder"),
        max_length=255,
        null=True,
        blank=True,
        help_text=_("CSS colour for a blank rect shown while awaiting image proper"),
    )
    etag = models.BinaryField(
        _("etag"),
        max_length=16,
        null=True,
        blank=True,
        editable=False,
        help_text=_("Hash of the image data when retrieved."),
    )
    retrieved = models.DateTimeField(
        _("retrieved"),
        null=True,
        blank=True,
    )

    created = models.DateTimeField(_("created"), default=timezone.now)
    modified = models.DateTimeField(_("modified"), auto_now=True)

    class Meta:
        verbose_name = _("image")
        verbose_name_plural = _("images")

    def __str__(self):
        last_part = self.data_url.rsplit("/", 1)[-1]
        if len(last_part) > 60:
            return "%s…%s" % (last_part[:30], last_part[-20:])
        return last_part

    def retrieve_data_task(self):
        """Celery signature to arrange for async download of this image."""
        from . import tasks

        return tasks.retrieve_image_data.s(
            self.pk,
            if_not_retrieved_since=(
                self.retrieved.timestamp() if self.retrieved else None
            ),
        )

    def queue_retrieve_data(self):
        """Arrange for async download of this image."""
        # Queue after transaction committed to avoid a race with the Celery queue.
        transaction.on_commit(self.retrieve_data_task().delay)

    @transaction.atomic
    def retrieve_data(self, if_not_retrieved_since=None, save=False):
        """Download the image data if available."""
        if self.retrieved and (
            not if_not_retrieved_since or if_not_retrieved_since < self.retrieved
        ):
            return
        self.retrieved = timezone.now()
        self.save()  # This will be rolled back in case of error but setting it now avoids some race conditons.

        if self.data_url.startswith("data:"):
            media_type, rest = self.data_url.split(";", 1)
            if rest.startswith("base64,"):
                data = b64decode(rest[7:])
            self.etag = md5(data).digest()
            file = ContentFile(data)
        else:
            r = requests.get(
                self.data_url, headers={"User-Agent": "Linotak/0.1 (thumbnailer)"}
            )
            media_type = r.headers["Content-Type"]
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
            # Sniff to get media_type for the file name.
            self._sniff(input=data, media_type=media_type)
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
        if save:
            self.save()

    def _sniff(self, media_type=None, **kwargs):
        """Given a file-like object, guess width, height, and media_type.

        Arguments --
            kwargs -- how to get the input. Either stdin=REALFILE or input=BYTES
        """
        try:
            self.media_type, self.width, self.height, self.placeholder = _sniff(
                media_type=media_type, **kwargs
            )
        except CannotSniff as e:
            rc, msg = e.args
            raise Image.NotSniffable(file_name_from_etag(self.etag, None), rc, msg)

    def delete_if_small(self):
        """If this image is small, delete it."""
        if (
            self.width
            and self.width < self.MIN_WIDTH
            and self.height
            and self.height < self.MIN_HEIGHT
        ):
            for r in self.representations.all():
                r.delete()
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

        has_crop = (
            self.crop_left > 0.0
            or self.crop_top > 0.0
            or self.crop_width < 1.0
            or self.crop_height < 1.0
        )
        if has_crop:
            crop_width = self.crop_width * self.width
            crop_height = self.crop_height * self.height
        else:
            crop_width, crop_height = self.width, self.height

        scaled, crop = spec.scale_and_crop_to_match(crop_width, crop_height)
        final_width, final_height = crop or scaled
        candidates = self.representations.filter(
            width=final_width, height=final_height
        )[:1]
        if candidates:
            # Already done!
            return candidates[0]

        if not has_crop and final_width == self.width and final_height == self.height:
            # Want the original size of the image. Just copy the data directly.
            rep = self.representations.create(
                media_type=self.media_type,
                width=self.width,
                height=self.height,
                is_cropped=bool(crop),
                etag=self.etag,
            )
            with self.cached_data.open() as f:
                rep.content.save(file_name_from_etag(rep.etag, rep.media_type), f)
            return

        cmd = ["convert", "-", "-resize", "%dx%d>" % scaled, "-"]
        if has_crop:
            x_c = int(round(self.width * self.crop_left))
            y_c = int(round(self.height * self.crop_top))
            w_c = int(round(self.width * self.crop_width))
            h_c = int(round(self.height * self.crop_height))
            cmd[2:2] = ["-crop", f"{w_c}x{h_c}+{x_c}+{y_c}", "+repage"]
        if crop:
            w_s, h_s = scaled
            w_c, h_c = crop
            x, y = round(self.focus_x * (w_s - w_c)), round(self.focus_y * (h_s - h_c))
            cmd[-1:-1] = ["-extent", "%dx%d+%d+%d" % (w_c, h_c, x, y)]
        with self.cached_data.open() as f:
            output = subprocess.run(
                cmd, check=True, stdin=f.file, stdout=subprocess.PIPE
            ).stdout
        etag = md5(output).digest()
        output_file = ContentFile(output)
        rep = self.representations.create(
            media_type=self.media_type,
            width=final_width,
            height=final_height,
            is_cropped=bool(crop),
            etag=etag,
        )
        rep.content.save(file_name_from_etag(rep.etag, rep.media_type), output_file)
        return rep

    def representation_task(self, spec):
        """Celery signature to arrange for representation to be created.

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
                self.representations.filter(
                    width__lte=final_width, height__lte=final_height
                ).order_by((F("width") * F("height")).desc())[:1]
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


GEOMETRY_RE = re.compile(r"(\d+)x(\d+)\+0\+0")


def _sniff(media_type=None, **kwargs):
    """Given a file-like object, guess media_type, width, and height.

    Arguments --
        kwargs -- how to get the input. Either stdin=REALFILE or input=BYTES

    Returns --
        MEDIA_TYPE, WIDTH, HEIGHT, PLACEHOLDER

    Raises --
        CannotSniff when cannot sniff
    """
    if media_type and "svg" in media_type:
        media_type_1, width, height, placeholder = _sniff_svg(**kwargs)
        if media_type_1:
            return media_type_1, width, height, placeholder
    cmd = ["identify", "-colorspace", "lab", "-verbose", "-"]
    result = subprocess.run(
        cmd, check=False, stderr=subprocess.PIPE, stdout=subprocess.PIPE, **kwargs
    )
    if result.returncode:
        # Command failed.
        raise CannotSniff(result.returncode, result.stderr or result.stdout)
    output = result.stdout
    media_type, geometry, l_bit, a_bit, b_bit = _comb_imagemagick_verbose(
        (
            ("Mime type",),
            ("Geometry",),
            ("Channel statistics", "Channel 0", "mean"),
            ("Channel statistics", "Channel 1", "mean"),
            ("Channel statistics", "Channel 2", "mean"),
        ),
        output,
    )
    if geometry and (m := GEOMETRY_RE.match(geometry)):
        width, height = int(m[1]), int(m[2])
    else:
        width, height = None, None
    lab = l_bit is not None and _lab_from_imagemagick_verbose_bits(
        (l_bit, a_bit, b_bit)
    )
    placeholder = "#%02X%02X%02X" % sRGB_from_Lab(lab) if lab else None
    return media_type, width, height, placeholder


_length_pattern = re.compile(r"^\s*(\d+|\d*\.\d+)\s*([a-z]{2,3})?\s*$")
_px_per_unit = {
    "px": 1.0,
    "pt": 96.0 / 72.0,
    "cm": 96.0 / 2.54,
    "mm": 96.0 / 25.4,
    "em": 16.0,  # Assume my usual 16px type size
    "ex": 16.0 / 2,  # Half an em
    "rem": 16.0,  # Ditto
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
        MEDIA_TYPE, WIDTH, HEIGHT, PLACEHOLDER
    """
    root = ElementTree.parse(stdin) if stdin else ElementTree.fromstring(input)
    width, height, view_box = root.get("width"), root.get("height"), root.get("viewBox")
    if width and height:
        width, height = px_from_length(width), px_from_length(height)
    elif view_box:
        width, height = view_box.split()[-2:]
        width, height = round(float(width)), round(float(height))
    else:
        width, height = None, None
    return (
        "image/svg+xml"
        if root.tag in ["{http://www.w3.org/2000/svg}svg", "svg"]
        else None,
        width,
        height,
        "#AAA",
    )


_media_types_by_imagemagick = {
    b"SVG": "image/svg+xml",
}


def media_type_from_imagemagick_type(type):
    """Given the type of image as reported by ImageMagick, return MIME type."""
    return (
        _media_types_by_imagemagick.get(type)
        or "image/%s" % type.decode("UTF-8").lower()
    )


_suffixes_by_media = {
    "image/svg+xml": ".svg",
}


def suffix_from_media_type(media_type):
    """Given an image MIME type, return file-name suffix."""
    if not media_type:
        return ".data"
    media_type = media_type.split(";", 1)[0]
    return _suffixes_by_media.get(media_type) or "." + media_type.split("/", 1)[1]


def file_name_from_etag(etag, media_type):
    return urlsafe_b64encode(etag).decode("ascii").rstrip("=") + suffix_from_media_type(
        media_type
    )


def _comb_imagemagick_verbose(specs, data):
    """Pull data items out of the output of `identify -colorspace lab -verbose`.

    Arguments --
        specs -- list of path, where a path is a list of headings
        data -- raw data as written by ImageMagick `identity -verbose`

    Returns --
        Sequence of values extracted from stream
        (value None means that value not found).
    """
    stream = io.TextIOWrapper(io.BytesIO(data), encoding="UTF-8", errors="replace")
    found = {tuple(p): None for p in specs}
    path = []
    indents = []
    indent = -1
    for line in stream:
        key, *rest = line.split(":", 1)
        len1 = len(key)
        key = key.lstrip()
        new_indent = len1 - len(key)
        while new_indent < indent:
            path = path[:-1]
            indent = indents.pop(-1)
        if new_indent == indent:
            path[-1] = key
        else:
            path.append(key)
            indents.append(indent)
            indent = new_indent
        p = tuple(path[1:])
        if p in found:
            found[p] = rest[0].strip()
    return tuple(found[tuple(p)] for p in specs)


# Picking a representative colour form an image to use as a placeholder.
#
# For now I am using the mean of the pixels, using the L*a*b* colourspace
# since its perceptually linear mapping form numbers to colours means the
# average colour should be closer to the average as perceieved by eye.
#
# Reluctant to get in to learning enough NumPy to write this directly, I am
# instead using ImageMagick’s colourspace transformation and statistics in the
# output of `identify -verbose`. I need to comb the verbose output for the
# values I want, and then convert from the transformed L*a*b* ImageMagick
# writes (the values are mapped from (0..255, -128..127, -182..127) to (0..1,
# 0..1, 0..1) by scaling and adding 0.5) back to sRGB.

COORD_RE = re.compile(r"\d*(?:.\d+)? \((0|1|0\.\d+)\)")


def _lab_from_imagemagick_verbose_bits(bits):
    """Extract L*a*b* coordinates from the format output by `identify -verbose`."""
    scaled_l, scaled_a, scaled_b = tuple(
        float(m[1]) for bit in bits if bit and (m := COORD_RE.match(bit))
    )
    return scaled_l * 100.0, scaled_a * 255.0 - 128.0, scaled_b * 255.0 - 128.0


def sRGB_from_Lab(lab):
    """Convert from CIE L*a*b* colour to 8-bit sRGB.

    Argument --
        lab -- a tuple of floats (L*, a*, b*) in range 0..100, -128..127, -128..127

    Returns --
        rgb -- a tuple of integers (r, g, b) in range 0..255

    """
    L_star, a_star, b_star = lab

    # Convert L*a*b* to XYZ
    delta = 6 / 29
    # D65 white point, scaled so XYZ are in range 0..1:
    X_n, Y_n, Z_n = (0.950489, 1.0, 1.088840)

    def f_minus_1(t):
        return t ** 3 if t > delta else 3 * delta * delta * (t - 4 / 29)

    q = (L_star + 16) / 116
    X = X_n * f_minus_1(q + a_star / 500)
    Y = Y_n * f_minus_1(q)
    Z = Z_n * f_minus_1(q - b_star / 200)

    # Convert XYZ to RGB linear in 0..1 scale
    R_L = 3.2406255 * X - 1.537208 * Y - 0.4986286 * Z
    G_L = -0.9689307 * X + 1.8757561 * Y + 0.0415175 * Z
    B_L = 0.0557101 * X - 0.2040211 * Y + 1.0569959 * Z

    return tuple(
        round(
            255 * (323 * u / 25 if u <= 0.0031308 else (211 * u ** (5 / 12) - 11) / 200)
        )
        for u in (R_L, G_L, B_L)
    )


class Representation(models.Model):
    """A representation of an image at a given size."""

    image = models.ForeignKey(
        Image,
        models.CASCADE,
        verbose_name="representation",
        related_name="representations",
        related_query_name="representation",
    )

    content = models.FileField(
        _("content"),
        upload_to="i",
        null=True,
        blank=True,
        help_text=_("Content of the image representation."),
    )
    media_type = models.CharField(
        _("media-type"),
        max_length=MAX_LENGTH,
        validators=[
            RegexValidator(r"^(image|application)/\w+(;\s*\w+=.*)?$"),
        ],
    )
    width = models.PositiveIntegerField(_("width"))
    height = models.PositiveIntegerField(_("height"))
    is_cropped = models.BooleanField(_("is cropped"))
    etag = models.BinaryField(
        _("etag"),
        max_length=16,
        editable=False,
        help_text=_("Hash of the image data when generated."),
    )

    created = models.DateTimeField(_("created"), default=timezone.now)
    modified = models.DateTimeField(_("modified"), auto_now=True)

    class Meta:
        verbose_name = "representation"
        verbose_name_plural = "representations"
        unique_together = [
            ("image", "width", "is_cropped"),
        ]

    def __str__(self):
        return "%s (%dx%d)" % (self.image, self.width, self.height)
