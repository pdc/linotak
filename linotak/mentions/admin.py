from django.contrib import admin

from .models import Incoming, Outgoing, Receiver, LocatorReceiver


class ReceiverAdmin(admin.ModelAdmin):
    list_display = ['url', 'created']
    search_fields = ['url']
    readonly_fields = ['created']
    date_hierarchy = 'created'


class LocatorReceiverAdmin(admin.ModelAdmin):
    list_display = ['locator', 'receiver', 'created']
    search_fields = ['locator__url', 'receiver__url']
    raw_id_fields = ['locator', 'receiver']
    date_hierarchy = 'created'


class OutgoingAdmin(admin.ModelAdmin):
    list_display = ['source', 'target', 'receiver', 'created']
    search_fields = ['source__text', 'target__url']
    raw_id_fields = ['source', 'target', 'receiver']
    readonly_fields = ['created']
    date_hierarchy = 'created'


class IncomingAdmin(admin.ModelAdmin):
    list_display = ['source_url', 'target', 'created']
    search_fields = ['source_url', 'target_url']
    raw_id_fields = ['source', 'target']
    date_hierarchy = 'created'


admin.site.register(Receiver, ReceiverAdmin)
admin.site.register(LocatorReceiver, LocatorReceiverAdmin)
admin.site.register(Outgoing, OutgoingAdmin)
admin.site.register(Incoming, IncomingAdmin)
