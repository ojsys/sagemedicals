from django.contrib import admin

from notifications.models import Notification, NotificationTemplate, OTPVerification


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("event_type", "channel", "is_active")
    list_filter = ("channel", "is_active")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("channel", "recipient", "event_type", "status", "sent_at")
    list_filter = ("channel", "status", "event_type")
    search_fields = ("recipient", "body")
    date_hierarchy = "created_at"
    readonly_fields = ("sent_at", "provider_reference", "error_message")


@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ("phone", "is_used", "attempts", "expires_at", "created_at")
    list_filter = ("is_used",)
    readonly_fields = ("code",)
