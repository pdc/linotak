"""Define admin interface for images."""

from django.contrib import admin
from django.utils.html import format_html

from .templatetags.image_representations import square_representation, representation
from .models import Image


def queue_retrieve(model_admin, request, queryset):
    """Queue the images to be retrieved."""
    for img in queryset:
        img.queue_retrieve_data()


queue_retrieve.short_description = 'Queue retrieval of image data'


def small_thumbnail(image):
    return format_html(
        '<div style="display: inline-block; background-color: #DED">'
        '{representation}</div>',
        representation=square_representation(image, 40) or '–')
    return


def large_thumbnail(image):
    return format_html(
        '<div style="display: inline-block; background-color: #DED">'
        '{representation}</div>',
        representation=representation(image, '320x320') or '–')


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
