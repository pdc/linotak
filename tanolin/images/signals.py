"""Signals that may be sent by models in this app."""

import django.dispatch


# Called when Image.widt and height needed and not available.
wants_data = django.dispatch.Signal(providing_args=["instance"])


# Called when Image.find_square_representation cannot find an exact match.
wants_square_representation = django.dispatch.Signal(providing_args=["instance", "size"])
