"""Define admin interface for images."""

from django.contrib import admin

from .models import Image


def queue_retrieve(model_admin, request, queryset):
    """Queue the images to be retrieved."""
    for img in queryset:
        img.queue_retrieve_data()


queue_retrieve.short_description = 'Queue retrieval of image data'


class ImageAdmin(admin.ModelAdmin):
    actions = [queue_retrieve]


admin.site.register(Image, ImageAdmin)
