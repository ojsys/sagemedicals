from django.contrib import admin

from laboratory.models import LabOrder, LabResult, LabTest


@admin.register(LabTest)
class LabTestAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "panel", "sample_type", "turnaround_hours", "price", "is_active")
    list_filter = ("sample_type", "is_active")
    search_fields = ("code", "name", "panel")

class LabResultInline(admin.StackedInline):
    model = LabResult
    extra = 0

@admin.register(LabOrder)
class LabOrderAdmin(admin.ModelAdmin):
    list_display = ("patient", "test", "priority", "status", "barcode", "created_at")
    list_filter = ("priority", "status")
    inlines = [LabResultInline]
