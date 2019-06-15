"""A simple value class for specifying the size and proportions of a representation of an image."""

import re


G_RE = re.compile(r'^\s*(\d+)\s*x\s*(\d+)\s*')
M_RE = re.compile(r'^(min|max)\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\s*')


class SizeSpec:
    __slots__ = 'width', 'height', 'min_ratio', 'max_ratio'

    def __init__(self, width, height, min_ratio=None, max_ratio=None):
        """Create an instance.

        Aerguments --
            width, height -- box the image will fit in to
            min_ratio (pair) -- image will be cropped if necessary to make it no taller than this
            max_ratio (pair) -- image will be cropped if necessary to make it no wider than this

        min_ratio and max_ratio are pairs of numbers (q,r) representing the rational number q/r.
        It only makes sense if min_ratio is no more than width:height
        and max_ratio no less than than width:heught.
        """
        self.width = width
        self.height = height
        self.min_ratio = min_ratio
        self.max_ratio = max_ratio

    @classmethod
    def of_square(cls, size):
        return cls(size, size, (1, 1), (1, 1))

    @classmethod
    def parse(cls, string):
        """Create instance from a summary in our little spec languag."""
        width = height = None
        min_ratio = max_ratio = None
        m = G_RE.search(string)
        if not m:
            raise ValueError('%r: size spec should start with WIDTHxHEIGHT' % string)
        width, height = int(m[1]), int(m[2])
        string = string[m.end(0):].lstrip()
        while string:
            m = M_RE.search(string)
            if not m:
                raise ValueError('%r: size spec not understood' % string)

            which, w, h = m[1], float(m[2]), float(m[3])
            if which == 'min':
                min_ratio = w, h
            else:
                max_ratio = w, h
            assert m.end(0) > 0
            string = string[m.end(0):]
        if width and height:
            return SizeSpec(width, height, min_ratio, max_ratio)

    def unparse(self):
        """Write a string in our little spec language."""
        parts = ['%dx%d' % (self.width, self.height)]
        if self.min_ratio:
            parts.append('min %g:%g' % self.min_ratio)
        if self.max_ratio:
            parts.append('max %g:%g' % self.max_ratio)
        return ' '.join(parts)

    def __str__(self):
        return self.unparse()

    def _unique(self):
        return self.width, self.height, self.min_ratio, self.max_ratio

    def __repr__(self):
        return '%s%r' % (self.__class__.__name__, self._unique())

    def __eq__(self, other):
        return self._unique() == other._unique()

    def enlarged(self, f):
        """Return size spec scaled up by this factor"""
        return SizeSpec(self.width * f, self.height * f, self.min_ratio, self.max_ratio)

    def scale_and_crop_to_match(self, source_width, source_height, allow_upscale=False):
        """Return dimensions of an reresentation satisfying criteria.

        Arguments --
            source_width, source_height -- dimensions of source image to be scaled to this size space
            allow_upscale -- will scale up image if required (default False)

        Returns (SCALED_WIDTH, SCALED_HEIGHT), CROPPED
            where (SCALED_WIDTH, SCALED_HEIGHT) is the size to scale the whole image to
            and CROPPED is (WIDTH, HEIGHT) to crop out of this scaled image,
            or None if the scaled image is already OK.
        """
        if source_width <= self.width and source_height <= self.height and not allow_upscale:
            return (source_width, source_height), None  # Do not scale up!
        if self.min_ratio:
            w, h = self.min_ratio
            if source_width * h < w * source_height:
                # Too narrow, so crop top and bottom.
                # scaling by height * w / h / source_width
                scaled_width = round(self.height * w / h)
                scaled = (scaled_width, round(source_height * self.height * w / h / source_width))
                cropped = (scaled_width, self.height)
                return scaled, cropped if cropped != scaled else None
        if self.max_ratio:
            w, h = self.max_ratio
            if source_width * h > w * source_height:
                # Too wide, so crop left and right.
                # Scaling by width * h / w / source_height
                scaled_height = round(self.width * h / w)
                scaled = (round(source_width * self.width * h / w / source_height), scaled_height)
                cropped = (self.width, scaled_height)
                return scaled, cropped if cropped != scaled else None
        if source_width * self.height > self.width * source_height:
            # Is wider than box. Shrink to fit.
            return (self.width, round(source_height * self.width / source_width)), None
        # Is taller than box. Shrink to fit.
        return (round(source_width * self.height / source_height), self.height), None

    def best_match(self, source_width, source_height):
        """Best match for an image of this source size.

        This may be cropped as well as scaled, depending on min_ratio and max_ratio.

        Returns WIDTH, HEIGHT
        """
        scaled, cropped = self.scale_and_crop_to_match(source_width, source_height)
        return cropped or scaled
