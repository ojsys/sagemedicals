"""
Insurance claims: NHIA and HMO claim lifecycle.
Claims are built from invoices and submitted to payers.
"""
from django.db import models

from core.models import BaseModel


class Payer(BaseModel):
    """An insurance payer — NHIA, or a named HMO."""

    class PayerType(models.TextChoices):
        NHIA = "nhia", "NHIA"
        HMO = "hmo", "HMO"
        EMPLOYER = "employer", "Employer Scheme"

    name = models.CharField(max_length=120)
    payer_type = models.CharField(max_length=20, choices=PayerType.choices)
    code = models.CharField(max_length=20, unique=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class ClaimBatch(BaseModel):
    """A submission batch sent to a payer for a given period."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        QUERIED = "queried", "Queried"
        APPROVED = "approved", "Approved"
        PAID = "paid", "Paid"
        REJECTED = "rejected", "Rejected"

    payer = models.ForeignKey(Payer, on_delete=models.PROTECT, related_name="batches")
    period_start = models.DateField()
    period_end = models.DateField()
    reference = models.CharField(max_length=80, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True,
        blank=True, related_name="+",
    )
    total_claimed = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_approved = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.payer} {self.period_start}–{self.period_end} [{self.get_status_display()}]"

    class Meta:
        ordering = ["-period_start"]

    def recalculate_total(self):
        from django.db.models import Sum
        total = self.claims.aggregate(t=Sum("claimed_amount"))["t"] or 0
        self.total_claimed = total
        self.save(update_fields=["total_claimed"])


class Claim(BaseModel):
    """A single patient encounter claim within a batch."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        QUERIED = "queried", "Queried"
        APPROVED = "approved", "Approved"
        PARTIAL = "partial", "Partially Approved"
        REJECTED = "rejected", "Rejected"

    batch = models.ForeignKey(
        ClaimBatch, on_delete=models.CASCADE, related_name="claims"
    )
    invoice = models.ForeignKey(
        "billing.Invoice", on_delete=models.PROTECT, related_name="claims"
    )
    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.PROTECT, related_name="claims"
    )
    claimed_amount = models.DecimalField(max_digits=12, decimal_places=2)
    approved_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    query_reason = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        unique_together = [("batch", "invoice")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Claim {self.pk} — {self.patient} ₦{self.claimed_amount}"


class HMOAuthorization(BaseModel):
    """Pre-authorisation from an HMO before services are rendered."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"
        EXPIRED = "expired", "Expired"

    payer = models.ForeignKey(
        Payer, on_delete=models.PROTECT, related_name="authorizations"
    )
    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.PROTECT, related_name="hmo_authorizations"
    )
    encounter = models.ForeignKey(
        "encounters.Encounter", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="hmo_authorizations",
    )
    authorization_code = models.CharField(max_length=60, blank=True)
    services_requested = models.TextField()
    approved_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    requested_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Auth {self.authorization_code or self.pk} — "
            f"{self.patient} ({self.get_status_display()})"
        )
