from django.apps import AppConfig


class ImagesConfig(AppConfig):
    name = 'linotak.images'

    def ready(self):
        from django.db.models.signals import post_save
        from .models import Image
        from .signals import wants_data, wants_representation
        from .signal_handlers import on_image_post_save, on_image_wants_data, on_image_wants_representation
        post_save.connect(on_image_post_save, sender=Image, dispatch_uid='on_image_post_save')
        wants_data.connect(on_image_wants_data, sender=Image, dispatch_uid='on_image_wants_data')
        wants_representation.connect(on_image_wants_representation, sender=Image, dispatch_uid='on_image_wants_representation')
