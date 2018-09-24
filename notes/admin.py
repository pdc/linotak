from django.contrib import admin
from .models import Person, Profile, Series, Note, Locator, NoteSubject


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


class LocatorAdmin(admin.ModelAdmin):
    search_fields = ['uri', 'title']



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
