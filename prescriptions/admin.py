from django.contrib import admin
from core.admin_mixins import SuperuserForceDeleteMixin

from prescriptions.models import Drug, DrugInteraction, Prescription


@admin.register(Drug)
class DrugAdmin(SuperuserForceDeleteMixin, admin.ModelAdmin):
    list_display = ("generic_name", "strength", "dosage_form", "category", "is_formulary", "is_active")
    list_filter = ("category", "dosage_form", "is_formulary", "is_active")
    search_fields = ("generic_name", "brand_name", "nafdac_number")

@admin.register(DrugInteraction)
class DrugInteractionAdmin(SuperuserForceDeleteMixin, admin.ModelAdmin):
    list_display = ("drug_a", "drug_b", "severity")
    list_filter = ("severity",)

@admin.register(Prescription)
class PrescriptionAdmin(SuperuserForceDeleteMixin, admin.ModelAdmin):
    list_display = ("drug", "patient", "dose", "frequency", "status", "prescriber")
    list_filter = ("status",)
