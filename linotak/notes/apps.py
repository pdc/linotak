from django.apps import AppConfig


class NotesConfig(AppConfig):
    name = "linotak.notes"

    def ready(self):
        """Wire uop signals for this app."""
        from django.db.models.signals import post_save
        from .models import Locator, on_locator_post_save

        post_save.connect(on_locator_post_save, sender=Locator)
