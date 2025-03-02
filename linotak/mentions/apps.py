from django.apps import AppConfig


class MentionsConfig(AppConfig):
    """Standard configration for the Linitak Mentions apps."""

    name = "linotak.mentions"

    def ready(self):
        """Wire up signals for this app."""
        from django.db.models.signals import post_save

        from ..notes.models import Locator, Note
        from ..notes.signals import locator_post_scanned
        from .models import handle_locator_post_scanned, handle_note_post_save

        post_save.connect(handle_note_post_save, sender=Note)
        locator_post_scanned.connect(handle_locator_post_scanned, sender=Locator)
