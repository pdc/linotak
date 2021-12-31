from django.apps import AppConfig


class MastodonConfig(AppConfig):
    name = "linotak.mastodon"

    def ready(self):
        """Wire up signals for this app."""
        from django.db.models.signals import post_save
        from ..notes.models import Note
        from .handlers import handle_note_post_save

        post_save.connect(handle_note_post_save, sender=Note)
