"""Define admin interface for images."""

from django.contrib import admin
from django.utils.html import format_html

from .models import Image
from .size_spec import SizeSpec


def queue_retrieve(model_admin, request, queryset):
    """Queue the images to be retrieved."""
    for img in queryset:
        img.queue_retrieve_data()


queue_retrieve.short_description = 'Queue retrieval of image data'


def thumbnail(image, size):
    rep = image.find_representation(size)
    if rep:
        return format_html(
            '<img src="{src}" width="{width}" height"{height}" alt="(thumbnail)"/>',
            src=rep.content.url, width=rep.width, height=rep.height)
    return '–'


def small_thumbnail(image):
    return thumbnail(image, SizeSpec.of_square(40))


def large_thumbnail(image):
    return thumbnail(image, SizeSpec(320, 320))


small_thumbnail.short_description = 'Thumbnail'
large_thumbnail.short_description = 'Thumbnail'


class ImageAdmin(admin.ModelAdmin):
    actions = [queue_retrieve]
    date_hierarchy = 'created'
    list_display = ['__str__', small_thumbnail, 'media_type', 'width', 'height', 'retrieved']
    list_filter = [
        'media_type',
        'retrieved',
    ]
    search_fields = ['data_url']
    readonly_fields = [large_thumbnail]



admin.site.register(Image, ImageAdmin)
