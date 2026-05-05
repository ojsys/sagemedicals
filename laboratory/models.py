from django.conf import settings
from django.db import models

from core.models import BaseModel


class LabTest(BaseModel):
    """Master catalogue of laboratory tests."""

    class SampleType(models.TextChoices):
        BLOOD = "blood", "Blood (Venous)"
        URINE = "urine", "Urine"
        STOOL = "stool", "Stool"
        SWAB = "swab", "Swab"
        SPUTUM = "sputum", "Sputum"
        CSF = "csf", "CSF"
        OTHER = "other", "Other"

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200, db_index=True)
    panel = models.CharField(max_length=100, blank=True)
    sample_type = models.CharField(max_length=10, choices=SampleType.choices, default=SampleType.BLOOD)
    turnaround_hours = models.PositiveSmallIntegerField(default=24)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    units = models.CharField(max_length=50, blank=True)
    reference_range_note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["panel", "name"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class LabOrder(BaseModel):
    class Priority(models.TextChoices):
        ROUTINE = "routine", "Routine"
        URGENT = "urgent", "Urgent"
        STAT = "stat", "STAT"

    class Status(models.TextChoices):
        ORDERED = "ordered", "Ordered"
        SAMPLE_COLLECTED = "sample_collected", "Sample Collected"
        IN_PROGRESS = "in_progress", "In Progress"
        RESULTED = "resulted", "Results Entered"
        VERIFIED = "verified", "Verified"
        RELEASED = "released", "Released to Clinician"
        REJECTED = "rejected", "Sample Rejected"
        CANCELLED = "cancelled", "Cancelled"

    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="lab_orders")
    encounter = models.ForeignKey(
        "encounters.Encounter", null=True, blank=True, on_delete=models.SET_NULL, related_name="lab_orders"
    )
    test = models.ForeignKey(LabTest, on_delete=models.PROTECT, related_name="orders")
    ordering_clinician = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="lab_orders"
    )
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.ROUTINE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ORDERED)
    clinical_notes = models.TextField(blank=True)
    barcode = models.CharField(max_length=50, blank=True, db_index=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="samples_collected"
    )
    rejection_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["patient", "status"]),
            models.Index(fields=["encounter"]),
        ]

    def __str__(self):
        return f"{self.test.name} — {self.patient} [{self.get_status_display()}]"


class LabResult(BaseModel):
    class AbnormalFlag(models.TextChoices):
        NORMAL = "normal", "Normal"
        LOW = "low", "Low"
        HIGH = "high", "High"
        CRITICAL_LOW = "critical_low", "Critical Low"
        CRITICAL_HIGH = "critical_high", "Critical High"
        ABNORMAL = "abnormal", "Abnormal (qualitative)"

    order = models.OneToOneField(LabOrder, on_delete=models.CASCADE, related_name="result")
    value = models.CharField(max_length=200)
    unit = models.CharField(max_length=50, blank=True)
    reference_low = models.CharField(max_length=50, blank=True)
    reference_high = models.CharField(max_length=50, blank=True)
    abnormal_flag = models.CharField(max_length=15, choices=AbnormalFlag.choices, default=AbnormalFlag.NORMAL)
    is_critical = models.BooleanField(default=False)
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="lab_results_entered"
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="lab_results_verified"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    critical_acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="critical_results_acknowledged"
    )
    critical_acknowledged_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.order.test.name}: {self.value} {self.unit}"
