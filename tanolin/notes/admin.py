from django.contrib import admin

from .models import Person, Profile, Series, Note, Locator, NoteSubject
from .tasks import fetch_locator_page


class SeriesAdmin(admin.ModelAdmin):
    pass


class NoteSubjectInline(admin.TabularInline):
    model = NoteSubject
    extra = 0


class NoteAdmin(admin.ModelAdmin):
    autocomplete_fields = ['subjects']
    inlines = [
        NoteSubjectInline
    ]


def queue_fetch(model_admin, request, queryset):
    """Queue the images to be retrieved."""
    for locator in queryset:
        fetch_locator_page.delay(locator.pk, if_not_scanned_since=locator.scanned)


queue_fetch.short_description = 'Queue fetch'


class LocatorAdmin(admin.ModelAdmin):
    search_fields = ['uri', 'title']
    actions = [queue_fetch]


class ProfileInline(admin.TabularInline):
    model = Profile
    extra = 0


class PersonAdmin(admin.ModelAdmin):
    search_fields = ['native_name']
    inlines = [
        ProfileInline
    ]


admin.site.register(Series, SeriesAdmin)
admin.site.register(Note, NoteAdmin)
admin.site.register(Locator, LocatorAdmin)
admin.site.register(Person, PersonAdmin)
