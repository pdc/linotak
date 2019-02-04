"""Define aformat for specifying how to filter notes."""

import re

_camel_word_re = re.compile(r'(.)([A-Z][a-z])')
_camel_prefix_re = re.compile(r'([a-z]+)([A-Z0-9])')
_whitespace_re = re.compile(r'\s+')
_title_word_re = re.compile(r'\b[A-Z][a-z]+\b')

_plus_minus_re = re.compile(r'([+-])')


def canonicalize_tag_name(proto_name):
    if not proto_name:
        raise ValueError('Tag name cannot be absent or empty')
    return proto_name.lower()


def wordify(proto_name):
    if not proto_name:
        raise ValueError('Tag name cannot be absent or empty')
    n = _camel_word_re.sub(r'\1 \2', proto_name)
    n = _camel_prefix_re.sub(r'\1 \2', n)
    n = _whitespace_re.sub(' ', n)
    if n[0].islower():
        n = _title_word_re.sub(lambda m: m.group(0).lower(), n)
    return n


class TagFilter:
    """Specification of how to filter notes."""

    __slots__ = 'included', 'excluded'

    def __init__(self, include=None, exclude=None):
        """Create instance with these reuirements.

        Arguments --
            include (list of string or None) -- tag names to include
            exclude (list of string or None) -- tag names to  exclude
        """
        self.included = set(include or [])
        self.excluded = set(exclude or [])

    @classmethod
    def parse(cls, string):
        """Create a TagFilter from this string.

        format:
            tagfilter = tag? ( [+-] tag )*
                where tag is the name of a tag (all lowercase, no spaces or dashes)

        Examples:
            foo  -- notes tagged foo
            foo+bar  -- notes tagged BOTH foo AND bar
            foo-bar  -- notes tagged foo AND NOT bar
            -bar  -- notes NOT tagged bar
        """
        if string:
            parts = _plus_minus_re.split(string)
            incl, excl = [], []
            first = parts.pop(0)
            if first:
                incl = [first]
            while parts:
                which = incl if parts.pop(0) == '+' else excl
                which.append(parts.pop(0))
            return TagFilter(incl, excl)

    def unparse(self):
        """Return the spec that will be parsed to this TagFilter instance."""
        positif = '+'.join(sorted(self.included))
        if self.excluded:
            return positif + '-' + '-'.join(sorted(self.excluded))
        return positif

    def apply(self, queryset, selector='tags__name'):
        """Apply this filter to this queryset."""
        for t in sorted(self.included):
            queryset = queryset.filter(**{selector: t})
        for t in sorted(self.excluded):
            queryset = queryset.exclude(**{selector: t})
        return queryset

    def __str__(self):
        return self.unparse()

    def __repr__(self):
        return '%s%r' % (type(self).__name__, self._unique())

    def __eq__(self, other):
        if not other:
            return False
        return self is other or self._unique() == other._unique()

    def __hash__(self):
        return hash(self._unique())

    def _unique(self):
        if self.excluded:
            return sorted(self.included or []), sorted(self.excluded)
        return sorted(self.included),
