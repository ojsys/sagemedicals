from django.conf import settings
from django.db import models

from core.models import BaseModel


class Order(BaseModel):
    """Abstract base for all clinical orders."""

    class OrderType(models.TextChoices):
        LAB = "lab", "Laboratory"
        IMAGING = "imaging", "Imaging"
        PRESCRIPTION = "prescription", "Prescription"
        PROCEDURE = "procedure", "Procedure"

    class Priority(models.TextChoices):
        ROUTINE = "routine", "Routine"
        URGENT = "urgent", "Urgent"
        STAT = "stat", "STAT"

    class Status(models.TextChoices):
        ORDERED = "ordered", "Ordered"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="+")
    encounter = models.ForeignKey("encounters.Encounter", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    ordering_clinician = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    order_type = models.CharField(max_length=20, choices=OrderType.choices)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.ROUTINE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ORDERED)
    ordered_at = models.DateTimeField(auto_now_add=True)
    clinical_notes = models.TextField(blank=True)

    class Meta:
        abstract = True
