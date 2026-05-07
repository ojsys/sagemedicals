from django.contrib import admin
from core.admin_mixins import SuperuserForceDeleteMixin

from scheduling.models import (
    Appointment,
    BlackoutDate,
    Clinic,
    ClinicSchedule,
    QueueEntry,
)


@admin.register(Clinic)
class ClinicAdmin(SuperuserForceDeleteMixin, admin.ModelAdmin):
    list_display = ("name", "department", "location", "is_active")
    list_filter = ("is_active",)

class BlackoutInline(admin.TabularInline):
    model = BlackoutDate
    extra = 0

@admin.register(ClinicSchedule)
class ClinicScheduleAdmin(SuperuserForceDeleteMixin, admin.ModelAdmin):
    list_display = ("clinic", "consultant", "start_time", "end_time", "slot_duration_minutes", "is_active")
    inlines = [BlackoutInline]

@admin.register(Appointment)
class AppointmentAdmin(SuperuserForceDeleteMixin, admin.ModelAdmin):
    list_display = ("patient", "clinic", "consultant", "date", "slot_time", "status", "priority")
    list_filter = ("status", "priority", "clinic")
    date_hierarchy = "date"

@admin.register(QueueEntry)
class QueueEntryAdmin(SuperuserForceDeleteMixin, admin.ModelAdmin):
    list_display = ("patient", "clinic", "date", "triage_level", "status", "is_walk_in")
    list_filter = ("triage_level", "status", "clinic")
    date_hierarchy = "date"
