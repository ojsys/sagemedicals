from django.conf import settings
from django.db import models

from core.models import BaseModel


class ServiceCatalogue(BaseModel):
    class Category(models.TextChoices):
        CONSULTATION = "consultation", "Consultation"
        LAB = "lab", "Laboratory"
        IMAGING = "imaging", "Imaging"
        PROCEDURE = "procedure", "Procedure"
        PHARMACY = "pharmacy", "Pharmacy"
        ADMISSION = "admission", "Admission / Bed"
        OTHER = "other", "Other"

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=Category.choices)
    self_pay_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    nhia_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hmo_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} (₦{self.self_pay_price})"

    def price_for_patient(self, patient):
        if patient.payer_type == "nhia":
            return self.nhia_price
        if patient.payer_type in ("private_hmo",):
            return self.hmo_price
        return self.self_pay_price


class Invoice(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        PARTIAL = "partial", "Partially Paid"
        PAID = "paid", "Paid"
        WAIVED = "waived", "Waived"
        VOID = "void", "Void"

    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="invoices")
    encounter = models.ForeignKey(
        "encounters.Encounter", null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices"
    )
    invoice_number = models.CharField(max_length=30, unique=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_reason = models.CharField(max_length=200, blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["patient", "status"])]

    def __str__(self):
        return f"{self.invoice_number} — {self.patient} (₦{self.total})"

    def recalculate(self):
        self.subtotal = sum(i.total for i in self.items.all())
        self.total = max(0, self.subtotal - self.discount)
        self.balance = max(0, self.total - self.amount_paid)
        if self.balance == 0 and self.total > 0:
            self.status = Invoice.Status.PAID
        elif self.amount_paid > 0:
            self.status = Invoice.Status.PARTIAL
        self.save(update_fields=["subtotal", "total", "balance", "status"])


class InvoiceItem(BaseModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    service = models.ForeignKey(ServiceCatalogue, null=True, blank=True, on_delete=models.SET_NULL)
    description = models.CharField(max_length=300)
    quantity = models.PositiveSmallIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} × {self.quantity} = ₦{self.total}"


class Payment(BaseModel):
    class Mode(models.TextChoices):
        CASH = "cash", "Cash"
        POS = "pos", "POS / Card"
        BANK_TRANSFER = "bank_transfer", "Bank Transfer"
        ONLINE = "online", "Online (Paystack)"
        WAIVER = "waiver", "Waiver"
        NHIA = "nhia", "NHIA"

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    mode = models.CharField(max_length=20, choices=Mode.choices)
    reference = models.CharField(max_length=100, blank=True)
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments_received"
    )
    received_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"₦{self.amount} {self.get_mode_display()} — {self.invoice}"


class PaystackTransaction(BaseModel):
    """Tracks an initiated Paystack payment from creation through verification."""

    class Status(models.TextChoices):
        PENDING   = "pending",   "Pending"
        SUCCESS   = "success",   "Success"
        FAILED    = "failed",    "Failed"
        ABANDONED = "abandoned", "Abandoned"

    invoice       = models.ForeignKey(
        Invoice, on_delete=models.PROTECT, related_name="paystack_transactions"
    )
    reference     = models.CharField(max_length=100, unique=True)
    amount_kobo   = models.PositiveIntegerField(help_text="Amount in kobo (naira × 100)")
    status        = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    paystack_id   = models.CharField(max_length=80, blank=True, help_text="Paystack transaction id")
    authorization_url = models.URLField(blank=True)
    customer_email = models.EmailField(blank=True)
    initiated_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="paystack_initiations",
    )
    verified_at   = models.DateTimeField(null=True, blank=True)
    gateway_response = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Paystack {self.reference} ₦{self.amount_kobo/100:.2f} [{self.get_status_display()}]"

    @property
    def amount_naira(self):
        return self.amount_kobo / 100
