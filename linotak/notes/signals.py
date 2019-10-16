"""Signals that may be sent."""

from django.dispatch import Signal


# Signal sent when a locator is scanned.
# Extra parameters --
#     instance -- the Locator instance in question
#     stuff -- list of pieces of information about the resource at this location
post_locator_scanned = Signal(providing_args=["instance", "stuff"])
