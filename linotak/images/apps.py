from django.apps import AppConfig


class ImagesConfig(AppConfig):
    name = 'linotak.images'

    def ready(self):
        from django.db.models.signals import post_save, pre_delete
        from .models import Image, Representation
        from .signals import wants_data, wants_representation
        from .signal_handlers import (
            on_image_post_save, on_image_wants_data, on_image_wants_representation,
            on_image_pre_delete, on_representation_pre_delete,
        )
        post_save.connect(on_image_post_save, sender=Image, dispatch_uid='on_image_post_save')
        wants_data.connect(on_image_wants_data, sender=Image, dispatch_uid='on_image_wants_data')
        wants_representation.connect(on_image_wants_representation, sender=Image, dispatch_uid='on_image_wants_representation')
        pre_delete.connect(on_image_pre_delete, sender=Image, dispatch_uid='on_image_pre_delete')
        pre_delete.connect(on_representation_pre_delete, sender=Representation, dispatch_uid='on_representation_pre_delete')
