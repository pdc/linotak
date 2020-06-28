from django.contrib import admin

from .models import Server, Connection


@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    serach_fields = 'name',
    readonly_fields = 'created', 'modified'


@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    search_fields = 'server__name', 'series__name', 'name'
    readonly_fields = 'created', 'modified'
