from django.contrib import admin

from .models import Connection, Post


@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    search_fields = 'series__name', 'domain', 'name'
    readonly_fields = 'created', 'modified'


@admin.register(Post)
class ConnectionAdmin(admin.ModelAdmin):
    search_fields = 'connection__series__name', 'connection__domain', 'connection__name'
    readonly_fields = 'created', 'modified'
