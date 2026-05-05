from django.contrib import admin

from admissions.models import (
    Admission,
    Bed,
    BedTransfer,
    MedicationAdministration,
    Room,
    Ward,
    WardRound,
)


class RoomInline(admin.TabularInline):
    model = Room
    extra = 1


class BedInline(admin.TabularInline):
    model = Bed
    extra = 1


@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    list_display = ("name", "ward_type", "floor", "is_active")
    list_filter = ("is_active",)
    inlines = [RoomInline]


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("ward", "name", "is_isolation")
    list_filter = ("ward",)
    inlines = [BedInline]


@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = ("label", "room", "status")
    list_filter = ("status", "room__ward")


class BedTransferInline(admin.TabularInline):
    model = BedTransfer
    extra = 0
    readonly_fields = ("transferred_at",)


class WardRoundInline(admin.TabularInline):
    model = WardRound
    extra = 0
    readonly_fields = ("round_at",)


@admin.register(Admission)
class AdmissionAdmin(admin.ModelAdmin):
    list_display = ("patient", "bed", "status", "admitted_at", "discharged_at")
    list_filter = ("status",)
    search_fields = ("patient__first_name", "patient__last_name", "patient__hospital_number")
    inlines = [BedTransferInline, WardRoundInline]


@admin.register(MedicationAdministration)
class MARAdmin(admin.ModelAdmin):
    list_display = ("admission", "prescription", "scheduled_at", "result", "administered_by")
    list_filter = ("result",)
