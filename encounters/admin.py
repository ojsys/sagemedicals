from django.contrib import admin

from encounters.models import Diagnosis, Encounter, Vitals


class VitalsInline(admin.StackedInline):
    model = Vitals
    extra = 0

class DiagnosisInline(admin.TabularInline):
    model = Diagnosis
    extra = 0

@admin.register(Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = ("patient", "encounter_type", "date_time", "attending", "status")
    list_filter = ("status", "encounter_type")
    inlines = [VitalsInline, DiagnosisInline]
    date_hierarchy = "date_time"
