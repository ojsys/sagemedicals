from django.contrib import admin
from core.admin_mixins import SuperuserForceDeleteMixin

from pharmacy.models import (
    Dispense,
    DispenseLine,
    DrugBatch,
    GoodsReceipt,
    GoodsReceiptLine,
    StockAdjustment,
    StockLevel,
    Store,
)


@admin.register(Store)
class StoreAdmin(SuperuserForceDeleteMixin, admin.ModelAdmin):
    list_display = ("name", "location", "is_main", "is_active")
    list_filter = ("is_active", "is_main")


class DrugBatchInline(admin.TabularInline):
    model = DrugBatch
    extra = 0
    readonly_fields = ("quantity_remaining",)


@admin.register(DrugBatch)
class DrugBatchAdmin(SuperuserForceDeleteMixin, admin.ModelAdmin):
    list_display = ("drug", "store", "batch_number", "expiry_date", "quantity_remaining", "is_quarantined")
    list_filter = ("store", "is_quarantined")
    search_fields = ("drug__generic_name", "batch_number")
    date_hierarchy = "expiry_date"


@admin.register(StockLevel)
class StockLevelAdmin(SuperuserForceDeleteMixin, admin.ModelAdmin):
    list_display = ("drug", "store", "quantity_on_hand", "reorder_level", "needs_reorder")
    list_filter = ("store",)
    search_fields = ("drug__generic_name",)


class GoodsReceiptLineInline(admin.TabularInline):
    model = GoodsReceiptLine
    extra = 1


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(SuperuserForceDeleteMixin, admin.ModelAdmin):
    list_display = ("pk", "store", "supplier", "received_date", "status")
    list_filter = ("store", "status")
    inlines = [GoodsReceiptLineInline]


class DispenseLineInline(admin.TabularInline):
    model = DispenseLine
    extra = 0


@admin.register(Dispense)
class DispenseAdmin(SuperuserForceDeleteMixin, admin.ModelAdmin):
    list_display = ("pk", "prescription", "store", "dispensed_by", "dispensed_at", "status")
    list_filter = ("store", "status")
    inlines = [DispenseLineInline]


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(SuperuserForceDeleteMixin, admin.ModelAdmin):
    list_display = ("store", "drug", "quantity_change", "reason", "adjusted_by", "created_at")
    list_filter = ("store", "reason")
