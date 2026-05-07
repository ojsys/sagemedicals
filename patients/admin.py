from django.contrib import admin
from core.admin_mixins import SuperuserForceDeleteMixin

from patients.models import Allergy, ChronicCondition, NextOfKin, Patient


class AllergyInline(admin.TabularInline):
    model = Allergy
    extra = 0
    fields = ("allergen", "allergy_type", "severity", "is_active")
    readonly_fields = ("created_at",)


class ConditionInline(admin.TabularInline):
    model = ChronicCondition
    extra = 0
    fields = ("icd10_code", "description", "status", "onset_date")


class NextOfKinInline(admin.StackedInline):
    model = NextOfKin
    extra = 0
    max_num = 1


@admin.register(Patient)
class PatientAdmin(SuperuserForceDeleteMixin, admin.ModelAdmin):
    list_display = ("hospital_number", "full_name", "age_display", "sex", "phone", "payer_type", "is_active")
    list_filter = ("sex", "payer_type", "is_active", "address_state")
    search_fields = ("hospital_number", "first_name", "last_name", "phone", "nhia_number")
    readonly_fields = ("hospital_number", "created_at", "updated_at")
    inlines = [AllergyInline, ConditionInline, NextOfKinInline]
    fieldsets = (
        ("Identity", {"fields": (
            "hospital_number", "first_name", "middle_name", "last_name",
            "date_of_birth", "sex", "gender_identity", "marital_status",
            "occupation", "religion", "ethnicity", "state_of_origin",
            "lga_of_origin", "preferred_language", "blood_group",
        )}),
        ("Contact", {"fields": ("phone", "phone_alt", "email", "address", "address_state", "address_lga")}),
        ("Payer", {"fields": ("payer_type", "nhia_number", "hmo_name", "hmo_plan", "corporate_employer")}),
        ("System", {"fields": ("photo", "user", "is_active")}),
    )
