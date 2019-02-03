from django.contrib import admin

from .models import Person, Profile, Series, Tag, Note, Locator, NoteSubject


class SeriesAdmin(admin.ModelAdmin):
    list_display = ['name', 'title', 'created', 'modified']


class TagAdmin(admin.ModelAdmin):
    search_fields = ['name', 'label']


class NoteSubjectInline(admin.TabularInline):
    model = NoteSubject
    extra = 0


class NoteAdmin(admin.ModelAdmin):
    autocomplete_fields = ['subjects']
    date_hierarchy = 'published'
    filter_horizontal = ['tags']
    inlines = [
        NoteSubjectInline
    ]
    list_display = ['__str__', 'series', 'author', 'published']
    list_filter = [
        'published',
    ]
    search_fields = ['text', 'subjects__url', 'tags__name']


def queue_fetch(model_admin, request, queryset):
    """Queue the images to be retrieved."""
    for locator in queryset:
        locator.queue_fetch()


queue_fetch.short_description = 'Queue fetch'


class LocatorAdmin(admin.ModelAdmin):
    date_hierarchy = 'created'
    search_fields = ['url', 'title']
    actions = [queue_fetch]
    raw_id_fields = ['images']
    list_display = ['__str__', 'title', 'scanned']
    list_filter = ['scanned']
    search_fields = ['url', 'title', 'text']


class ProfileInline(admin.TabularInline):
    model = Profile
    extra = 0


class PersonAdmin(admin.ModelAdmin):
    search_fields = ['native_name']
    inlines = [
        ProfileInline
    ]


admin.site.register(Series, SeriesAdmin)
admin.site.register(Tag, TagAdmin)
admin.site.register(Note, NoteAdmin)
admin.site.register(Locator, LocatorAdmin)
admin.site.register(Person, PersonAdmin)
