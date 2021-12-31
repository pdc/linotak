from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Incoming, Outgoing, Receiver, LocatorReceiver


def queue_fetch_source(model_admin, request, queryset):
    """Queue the images to be retrieved."""
    for incomming in queryset:
        incomming.source.queue_fetch()


queue_fetch_source.short_description = _("Queue fetch source")


class ReceiverAdmin(admin.ModelAdmin):
    list_display = ["url", "created"]
    search_fields = ["url"]
    readonly_fields = ["created"]
    date_hierarchy = "created"


class LocatorReceiverAdmin(admin.ModelAdmin):
    list_display = ["locator", "receiver", "created"]
    search_fields = ["locator__url", "receiver__url"]
    raw_id_fields = ["locator", "receiver"]
    date_hierarchy = "created"


class OutgoingAdmin(admin.ModelAdmin):
    list_display = ["source", "target", "receiver", "created"]
    search_fields = ["source__text", "target__url"]
    raw_id_fields = ["source", "target", "receiver"]
    readonly_fields = ["created"]
    date_hierarchy = "created"


class IncomingAdmin(admin.ModelAdmin):
    list_display = ["source_url", "target", "intent", "received"]
    search_fields = ["source_url", "target_url", "target__text"]
    raw_id_fields = ["source", "target"]
    date_hierarchy = "received"
    actions = [queue_fetch_source]


admin.site.register(Receiver, ReceiverAdmin)
admin.site.register(LocatorReceiver, LocatorReceiverAdmin)
admin.site.register(Outgoing, OutgoingAdmin)
admin.site.register(Incoming, IncomingAdmin)
