from django.apps import AppConfig


class ImagesConfig(AppConfig):
    name = 'tanolin.images'

    def ready(self):
        from django.db.models.signals import post_save
        from .models import Image
        from .signals import on_image_post_save

        post_save.connect(on_image_post_save, sender=Image)
