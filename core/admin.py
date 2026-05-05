from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse

from core.models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = [
        ("Identity", {
            "fields": ["hospital_name", "short_name", "tagline"],
        }),
        ("Logos & Favicon", {
            "fields": ["logo", "logo_on_light", "favicon"],
            "description": (
                "Upload a transparent PNG logo. "
                "The primary logo is used in the dark sidebar and patient portal; "
                "the light-background logo is used on invoices and printed documents."
            ),
        }),
        ("Contact Details", {
            "fields": ["phone", "email", "address", "website"],
        }),
        ("Regulatory & Compliance", {
            "fields": ["nhia_code", "accreditation", "rc_number"],
            "classes": ["collapse"],
        }),
        ("Documents", {
            "fields": ["footer_note"],
            "classes": ["collapse"],
        }),
    ]

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Redirect the list view straight to the edit form (singleton UX).
        obj, _ = SiteSettings.objects.get_or_create(pk=1)
        return HttpResponseRedirect(
            reverse("admin:core_sitesettings_change", args=[obj.pk])
        )
