"""Signals that may be sent by models in this app."""

import django.dispatch


# Called when `Image.width` and `height` needed and not available.
# Argument:
#     `instance` – the `Image` instance
wants_data = django.dispatch.Signal()


# Called when `Image.find_square_representation` cannot find an exact match.
# Argument:
#   `instance` – the Image instance
#   `size_spec` – specifies the size wanted
wants_representation = django.dispatch.Signal()
