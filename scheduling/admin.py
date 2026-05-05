from django.contrib import admin

from scheduling.models import (
    Appointment,
    BlackoutDate,
    Clinic,
    ClinicSchedule,
    QueueEntry,
)


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "location", "is_active")
    list_filter = ("is_active",)

class BlackoutInline(admin.TabularInline):
    model = BlackoutDate
    extra = 0

@admin.register(ClinicSchedule)
class ClinicScheduleAdmin(admin.ModelAdmin):
    list_display = ("clinic", "consultant", "start_time", "end_time", "slot_duration_minutes", "is_active")
    inlines = [BlackoutInline]

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("patient", "clinic", "consultant", "date", "slot_time", "status", "priority")
    list_filter = ("status", "priority", "clinic")
    date_hierarchy = "date"

@admin.register(QueueEntry)
class QueueEntryAdmin(admin.ModelAdmin):
    list_display = ("patient", "clinic", "date", "triage_level", "status", "is_walk_in")
    list_filter = ("triage_level", "status", "clinic")
    date_hierarchy = "date"
