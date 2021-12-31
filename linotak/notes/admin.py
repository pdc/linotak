from django.contrib import admin
from django.utils.html import format_html

from ..images.templatetags.image_representations import square_representation
from .models import (
    Person,
    Profile,
    Series,
    Tag,
    Note,
    NoteSubject,
    Locator,
    LocatorImage,
)


class SeriesAdmin(admin.ModelAdmin):
    list_display = ["name", "title", "created", "modified"]
    raw_id_fields = ["icon", "apple_touch_icon"]


class TagAdmin(admin.ModelAdmin):
    search_fields = ["name", "label"]


class NoteSubjectInline(admin.TabularInline):
    model = NoteSubject
    extra = 0
    raw_id_fields = ["locator"]


class NoteAdmin(admin.ModelAdmin):
    autocomplete_fields = ["subjects"]
    date_hierarchy = "published"
    filter_horizontal = ["tags"]
    inlines = [
        NoteSubjectInline,
    ]
    list_display = ["__str__", "series", "author", "published"]
    list_filter = [
        "published",
    ]
    search_fields = ["text", "subjects__url", "tags__name"]


def queue_fetch(model_admin, request, queryset):
    """Queue the images to be retrieved."""
    for locator in queryset:
        locator.queue_fetch()


queue_fetch.short_description = "Queue fetch"


def image_thumbnail(locator_image):
    return format_html(
        '<div style="display: inline-block; background-color: #DED">'
        "{representation}</div>",
        representation=square_representation(locator_image.image, 40) or "–",
    )
    return


image_thumbnail.short_description = "Thumbnail"


def image_size(locator_image):
    if not locator_image.image.width or not locator_image.image.height:
        return "–"
    return "%d\u2009×\u2009%d" % (locator_image.image.width, locator_image.image.height)


image_size.short_description = "Image size"


class LocatorImageInline(admin.TabularInline):
    model = LocatorImage
    extra = 0
    raw_id_fields = ["image"]
    readonly_fields = [image_thumbnail, image_size]


class LocatorAdmin(admin.ModelAdmin):
    date_hierarchy = "created"
    search_fields = ["url", "title"]
    actions = [queue_fetch]
    inlines = [
        LocatorImageInline,
    ]
    list_display = ["__str__", "title", "scanned"]
    list_filter = ["scanned"]
    search_fields = ["url", "title", "text"]
    raw_id_fields = ["via"]


class ProfileInline(admin.TabularInline):
    model = Profile
    extra = 0


class PersonAdmin(admin.ModelAdmin):
    list_display = ["__str__", "slug"]
    search_fields = ["native_name", "description", "slug"]
    inlines = [ProfileInline]
    raw_id_fields = ["image"]
    readonly_fields = [image_thumbnail, image_size]


admin.site.register(Series, SeriesAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(Note, NoteAdmin)
admin.site.register(Locator, LocatorAdmin)
admin.site.register(Person, PersonAdmin)
