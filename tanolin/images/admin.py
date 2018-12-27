"""Define admin interface for images."""

from django.contrib import admin

from .models import Image
from .tasks import retrieve_image_data


def queue_retrieve(model_admin, request, queryset):
    """Queue the images to be retrieved."""
    for img in queryset:
        retrieve_image_data.delay(img.pk, if_not_retrieved_since=img.retrieved)


queue_retrieve.short_description = 'Queue retrieval of image data'


class ImageAdmin(admin.ModelAdmin):
    actions = [queue_retrieve]


admin.site.register(Image, ImageAdmin)
