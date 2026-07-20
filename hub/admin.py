from django.contrib import admin

from .models import (
    BotConversationState,
    Designer,
    DesignerSessionToken,
    HubBrief,
    HubBriefEvent,
    SiteNode,
)


@admin.register(SiteNode)
class SiteNodeAdmin(admin.ModelAdmin):
    list_display = ("name", "site_id", "is_active", "created_at")
    search_fields = ("name", "site_id")
    list_filter = ("is_active",)


@admin.register(Designer)
class DesignerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "max_user_id", "web_login", "sbp_phone", "is_active", "registered_at")
    search_fields = ("full_name", "max_user_id", "web_login", "sbp_phone")
    list_filter = ("is_active",)


@admin.register(HubBrief)
class HubBriefAdmin(admin.ModelAdmin):
    list_display = ("public_id", "brief_number", "site", "status", "designer", "agreed_price", "updated_at")
    search_fields = ("public_id", "brief_number", "client_ref")
    list_filter = ("status", "site")
    autocomplete_fields = ("designer",)
    readonly_fields = ("created_at", "updated_at", "done_at", "source_stl_file", "stl_sync_error")


@admin.register(HubBriefEvent)
class HubBriefEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "brief", "event", "delivered_ok", "created_at")
    search_fields = ("event_id", "brief__public_id", "event")
    list_filter = ("event", "delivered_ok")


@admin.register(BotConversationState)
class BotConversationStateAdmin(admin.ModelAdmin):
    list_display = ("max_user_id", "state", "updated_at")
    search_fields = ("max_user_id", "full_name", "sbp_phone")


@admin.register(DesignerSessionToken)
class DesignerSessionTokenAdmin(admin.ModelAdmin):
    list_display = ("designer", "key", "expires_at", "is_revoked", "created_at")
    search_fields = ("designer__full_name", "designer__max_user_id", "key")
    list_filter = ("is_revoked",)
