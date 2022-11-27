from datetime import datetime, timezone
from django.utils.timezone import make_aware


def datetime_of_timestamp(timestamp):
    """Given seconds since the epoch, return a timezone-aware datetime instance."""
    if timestamp:
        return make_aware(datetime.utcfromtimestamp(timestamp), timezone.utc)
