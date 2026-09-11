from django.contrib import admin

from core.admin_mixins import SuperuserForceDeleteMixin

from .models import BirthRecord


@admin.register(BirthRecord)
class BirthRecordAdmin(SuperuserForceDeleteMixin, admin.ModelAdmin):
    list_display = [
        "certificate_number", "child_name", "sex", "date_of_birth",
        "time_of_birth", "weight_kg", "mother",
    ]
    list_filter = ["sex", "delivery_mode"]
    search_fields = [
        "certificate_number", "child_first_name", "child_surname",
        "mother__first_name", "mother__last_name", "mother__hospital_number",
    ]
    raw_id_fields = ["mother", "anc_record", "attended_by"]
    readonly_fields = ["certificate_number"]
    list_select_related = ["mother"]
    date_hierarchy = "date_of_birth"
    fieldsets = [
        ("Certificate", {"fields": ["certificate_number", "mother", "anc_record"]}),
        ("Child", {"fields": [
            "child_first_name", "child_middle_name", "child_surname", "sex",
        ]}),
        ("Birth", {"fields": [
            "date_of_birth", "time_of_birth", "weight_kg", "length_cm",
            "gestational_age_weeks", "delivery_mode", "birth_order", "babies_in_delivery",
        ]}),
        ("Parents & Attendant", {"fields": ["father_name", "attended_by"]}),
        ("Notes", {"fields": ["notes"], "classes": ["collapse"]}),
    ]

    @admin.display(description="Child", ordering="child_first_name")
    def child_name(self, obj):
        return obj.child_full_name
