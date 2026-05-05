from django.contrib import admin

from portal.models import PortalAppointmentRequest, PortalFeedback, PortalSession


@admin.register(PortalSession)
class PortalSessionAdmin(admin.ModelAdmin):
    list_display = ("patient", "expires_at", "last_active", "ip_address")
    readonly_fields = ("token",)


@admin.register(PortalAppointmentRequest)
class PortalAppointmentRequestAdmin(admin.ModelAdmin):
    list_display = ("patient", "preferred_date", "clinic", "status", "reviewed_by")
    list_filter = ("status",)
    actions = ["mark_booked", "mark_declined"]

    @admin.action(description="Mark selected requests as Booked")
    def mark_booked(self, request, queryset):
        queryset.update(status=PortalAppointmentRequest.Status.BOOKED)

    @admin.action(description="Mark selected requests as Declined")
    def mark_declined(self, request, queryset):
        queryset.update(status=PortalAppointmentRequest.Status.DECLINED)


@admin.register(PortalFeedback)
class PortalFeedbackAdmin(admin.ModelAdmin):
    list_display = ("patient", "encounter", "rating", "created_at")
    list_filter = ("rating",)
