from django.contrib import admin

from integrations.models import Claim, ClaimBatch, HMOAuthorization, Payer


@admin.register(Payer)
class PayerAdmin(admin.ModelAdmin):
    list_display = ("name", "payer_type", "code", "is_active")
    list_filter = ("payer_type", "is_active")


class ClaimInline(admin.TabularInline):
    model = Claim
    extra = 0
    readonly_fields = ("invoice", "patient", "claimed_amount", "approved_amount", "status")


@admin.register(ClaimBatch)
class ClaimBatchAdmin(admin.ModelAdmin):
    list_display = (
        "payer", "period_start", "period_end", "status",
        "total_claimed", "total_approved",
    )
    list_filter = ("payer", "status")
    inlines = [ClaimInline]


@admin.register(HMOAuthorization)
class HMOAuthorizationAdmin(admin.ModelAdmin):
    list_display = (
        "authorization_code", "payer", "patient", "status",
        "valid_from", "valid_until", "approved_amount",
    )
    list_filter = ("payer", "status")
    search_fields = ("authorization_code", "patient__first_name", "patient__last_name")
