"""Define admin interface for images."""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .templatetags.image_representations import square_representation, representation
from .models import Image, Representation


def queue_retrieve(model_admin, request, queryset):
    """Queue the images to be retrieved."""
    for img in queryset:
        img.queue_retrieve_data()


queue_retrieve.short_description = _('Queue retrieval of image data')


def sniff_again(model_admin, request, queryset):
    """Delete images if they are less than 80×80 pixels."""
    for image in queryset.filter(cached_data__isnull=False):
        image.sniff()
        image.save()


sniff_again.short_description = _('Sniff again')


def delete_cropped_representations(model_admin, request, queryset):
    """Delete representations that are cropped (e.g., because focus changed)."""
    Representation.objects.filter(image__in=queryset, is_cropped=True).delete()


delete_cropped_representations.short_description = _('Delete cropped representations')


def delete_all_representations(model_admin, request, queryset):
    """Delete representations, forcing them to be regenerated."""
    Representation.objects.filter(image__in=queryset).delete()


delete_all_representations.short_description = _('Delete all representations')


def delete_if_small(model_admin, request, queryset):
    """Delete images if they are less than 80×80 pixels."""
    for image in queryset.all():
        image.delete_if_small()


delete_if_small.short_description = _('Delete if small')


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


small_thumbnail.short_description = _('Thumbnail')
large_thumbnail.short_description = _('Thumbnail')


class ImageAdmin(admin.ModelAdmin):
    actions = [queue_retrieve, sniff_again, delete_cropped_representations, delete_all_representations, delete_if_small]
    date_hierarchy = 'created'
    list_display = ['__str__', small_thumbnail, 'media_type', 'width', 'height', 'retrieved']
    list_filter = [
        'media_type',
        'retrieved',
    ]
    search_fields = ['data_url']
    readonly_fields = [large_thumbnail]


admin.site.register(Image, ImageAdmin)
