from django.db import models
from django.utils import timezone

from core.models import BaseModel
from prescriptions.models import Drug


class Store(BaseModel):
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=120, blank=True)
    is_main = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class DrugBatch(BaseModel):
    """A received batch of a drug with expiry tracking."""

    drug = models.ForeignKey(Drug, on_delete=models.PROTECT, related_name="batches")
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="batches")
    batch_number = models.CharField(max_length=80)
    expiry_date = models.DateField()
    quantity_received = models.PositiveIntegerField()
    quantity_remaining = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    supplier = models.CharField(max_length=120, blank=True)
    received_at = models.DateTimeField(default=timezone.now)
    received_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    is_quarantined = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.drug} — {self.batch_number} (exp {self.expiry_date})"

    class Meta:
        ordering = ["expiry_date"]
        unique_together = [("drug", "batch_number", "store")]
        indexes = [
            models.Index(fields=["drug", "store", "expiry_date"]),
            models.Index(fields=["expiry_date"]),
        ]


class StockLevel(BaseModel):
    """Aggregate on-hand quantity per drug per store (kept in sync by signals)."""

    drug = models.ForeignKey(Drug, on_delete=models.PROTECT, related_name="stock_levels")
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="stock_levels")
    quantity_on_hand = models.IntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=0)
    reorder_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("drug", "store")]

    def __str__(self):
        return f"{self.drug} @ {self.store}: {self.quantity_on_hand}"

    @property
    def needs_reorder(self):
        return self.quantity_on_hand <= self.reorder_level


class GoodsReceipt(BaseModel):
    """Purchase order / goods-received note."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        RECEIVED = "received", "Received"
        PARTIAL = "partial", "Partial"

    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="goods_receipts")
    supplier = models.CharField(max_length=120)
    invoice_reference = models.CharField(max_length=80, blank=True)
    received_date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True)
    received_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="+"
    )

    def __str__(self):
        return f"GRN-{self.pk} {self.supplier} {self.received_date}"


class GoodsReceiptLine(BaseModel):
    receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name="lines")
    drug = models.ForeignKey(Drug, on_delete=models.PROTECT)
    batch_number = models.CharField(max_length=80)
    expiry_date = models.DateField()
    quantity_ordered = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["drug__generic_name"]


class Dispense(BaseModel):
    """Dispensing event — ties a Prescription to batch draws."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DISPENSED = "dispensed", "Dispensed"
        RETURNED = "returned", "Returned"

    prescription = models.OneToOneField(
        "prescriptions.Prescription", on_delete=models.PROTECT, related_name="dispense"
    )
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="dispenses")
    dispensed_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    dispensed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Dispense #{self.pk} — {self.prescription}"


class DispenseLine(BaseModel):
    """FEFO batch draw for a dispense."""

    dispense = models.ForeignKey(Dispense, on_delete=models.CASCADE, related_name="lines")
    batch = models.ForeignKey(DrugBatch, on_delete=models.PROTECT, related_name="dispense_lines")
    quantity = models.PositiveIntegerField()

    class Meta:
        ordering = ["batch__expiry_date"]


class StockAdjustment(BaseModel):
    """Manual stock correction (damage, theft, stocktake variance)."""

    class Reason(models.TextChoices):
        STOCKTAKE = "stocktake", "Stocktake Variance"
        DAMAGE = "damage", "Damage / Breakage"
        EXPIRY = "expiry", "Expiry Write-off"
        THEFT = "theft", "Theft / Loss"
        TRANSFER = "transfer", "Inter-store Transfer"
        OTHER = "other", "Other"

    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="adjustments")
    drug = models.ForeignKey(Drug, on_delete=models.PROTECT, related_name="adjustments")
    batch = models.ForeignKey(
        DrugBatch, on_delete=models.PROTECT, null=True, blank=True, related_name="adjustments"
    )
    quantity_change = models.IntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    notes = models.TextField(blank=True)
    adjusted_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]
