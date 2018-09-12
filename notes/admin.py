from django.contrib import admin
from .models import Series, Note


class SeriesAdmin(admin.ModelAdmin):
    pass


class NoteAdmin(admin.ModelAdmin):
    pass


admin.site.register(Series, SeriesAdmin)
admin.site.register(Note, NoteAdmin)
