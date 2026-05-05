from django.contrib import admin

from surgery.models import SurgeryBooking, SurgeryTeamMember, Theatre


class TeamInline(admin.TabularInline):
    model = SurgeryTeamMember
    extra = 1


@admin.register(Theatre)
class TheatreAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "is_active")


@admin.register(SurgeryBooking)
class SurgeryBookingAdmin(admin.ModelAdmin):
    list_display = (
        "procedure_name", "patient", "theatre", "lead_surgeon",
        "scheduled_date", "scheduled_time", "priority", "status",
    )
    list_filter = ("status", "priority", "theatre")
    search_fields = ("patient__first_name", "patient__last_name", "procedure_name")
    date_hierarchy = "scheduled_date"
    inlines = [TeamInline]
