"""Matchers for use in mock functions’ argument lists."""


from .utils import datetime_of_timestamp


class DateTimeTimestampMatcher:
    """Helper for comparing mock argument lists to a timestamp.

    We want a timestamp (seconds since 1970-01-01)
    that when translated to a datetime instance matches the
    datetime we first thought of.
    """

    def __init__(self, expected):
        self.expected = expected

    def __eq__(self, other):
        """Check this value will be translated to the same datetime as expected."""
        actual = datetime_of_timestamp(other)
        return actual == self.expected
