from base64 import b64encode
from datetime import datetime, timezone
from urllib.parse import quote


def datetime_of_timestamp(timestamp):
    """Given seconds since the epoch, return a timezone-aware datetime instance."""
    if timestamp:
        return datetime.fromtimestamp(timestamp, timezone.utc)


def create_data_url(media_type, data, base64=None):
    """Generate an RFC-2397-compliant data URL."""
    type, *parts = media_type.split(";")
    params = [
        (k.strip(), v.strip().strip('"')) for k, v in (x.split("=") for x in parts)
    ]
    munged_media_type = ";".join(
        [type.strip()] + [quote(k) + "=" + quote(v) for k, v in params]
    )

    if base64 is None:
        base64 = isinstance(data, bytes)

    if base64:
        if isinstance(data, str):
            data = data.encode("UTF-8")
        encoded_data = b64encode(data).decode()
        return f"data:{munged_media_type};base64,{encoded_data}"

    if isinstance(data, bytes):
        # Given caller has overridden base64 flag, assume this is UTF-8 (or USASCII) text.
        data = data.decode("UTF-8")
    encoded_data = quote(data, encoding="UTF-8")
    return f"data:{munged_media_type},{encoded_data}"
