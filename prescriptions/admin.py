from django.contrib import admin

from prescriptions.models import Drug, DrugInteraction, Prescription


@admin.register(Drug)
class DrugAdmin(admin.ModelAdmin):
    list_display = ("generic_name", "strength", "dosage_form", "category", "is_formulary", "is_active")
    list_filter = ("category", "dosage_form", "is_formulary", "is_active")
    search_fields = ("generic_name", "brand_name", "nafdac_number")

@admin.register(DrugInteraction)
class DrugInteractionAdmin(admin.ModelAdmin):
    list_display = ("drug_a", "drug_b", "severity")
    list_filter = ("severity",)

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ("drug", "patient", "dose", "frequency", "status", "prescriber")
    list_filter = ("status",)
