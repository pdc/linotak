from datetime import datetime
from django.utils import timezone


def datetime_of_timestamp(timestamp):
    """Given seconds since the epoch, return a timezone-aware datetime instance."""
    if timestamp:
        return timezone.make_aware(datetime.utcfromtimestamp(timestamp), timezone.utc)
