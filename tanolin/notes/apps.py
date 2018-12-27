from django.apps import AppConfig


class NotesConfig(AppConfig):
    name = 'tanolin.notes'

    def ready(self):
        from django.db.models.signals import post_save
        from .models import Locator
        from .signals import on_locator_post_save

        post_save.connect(on_locator_post_save, sender=Locator)
