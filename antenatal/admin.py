from django.contrib import admin

from .models import ANCRecord, ANCVisit, ObstetricScan


class ANCVisitInline(admin.StackedInline):
    model = ANCVisit
    extra = 1
    fields = [
        "visit_date", "gestational_age_weeks",
        "weight_kg", "bp_systolic", "bp_diastolic",
        "fundal_height_cm", "fetal_heart_rate",
        "presentation", "urine_protein", "urine_glucose",
        "next_visit_date",
        "diagnosis", "plan", "notes",
    ]
    ordering = ["-visit_date"]


class ObstetricScanInline(admin.StackedInline):
    model = ObstetricScan
    extra = 0
    fields = [
        "scan_date", "gestational_age_weeks", "gestational_age_days",
        "placenta_location", "amniotic_fluid",
        "findings", "impression", "report_file",
    ]
    ordering = ["-scan_date"]


@admin.register(ANCRecord)
class ANCRecordAdmin(admin.ModelAdmin):
    list_display = [
        "patient", "edd", "gestational_age_today", "gravida_para",
        "booking_date", "is_active",
    ]
    list_filter = ["is_active", "rhesus", "blood_group"]
    search_fields = [
        "patient__first_name", "patient__last_name",
        "patient__hospital_number",
    ]
    autocomplete_fields = ["patient"]
    list_select_related = ["patient"]
    date_hierarchy = "edd"
    inlines = [ANCVisitInline, ObstetricScanInline]
    fieldsets = [
        ("Patient", {"fields": ["patient", "is_active"]}),
        ("Pregnancy Dates", {"fields": ["lmp", "edd", "booking_date"]}),
        ("Obstetric History", {"fields": ["gravida", "para"]}),
        ("Investigations", {"fields": ["blood_group", "rhesus"]}),
        ("Notes", {"fields": ["notes"], "classes": ["collapse"]}),
    ]

    @admin.display(description="G/P")
    def gravida_para(self, obj):
        return f"G{obj.gravida}P{obj.para}"

    @admin.display(description="GA today")
    def gestational_age_today(self, obj):
        return f"{obj.gestational_age_weeks}+{obj.gestational_age_days} wks"
