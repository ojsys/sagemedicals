from django.db import models
from django.utils import timezone

from core.models import BaseModel


class Theatre(BaseModel):
    name = models.CharField(max_length=80)
    location = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class SurgeryBooking(BaseModel):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        CONFIRMED = "confirmed", "Confirmed"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        POSTPONED = "postponed", "Postponed"

    class Priority(models.TextChoices):
        ELECTIVE = "elective", "Elective"
        URGENT = "urgent", "Urgent"
        EMERGENCY = "emergency", "Emergency"

    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.PROTECT, related_name="surgery_bookings"
    )
    admission = models.ForeignKey(
        "admissions.Admission", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="surgeries",
    )
    theatre = models.ForeignKey(
        Theatre, on_delete=models.PROTECT, related_name="bookings"
    )
    lead_surgeon = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True,
        related_name="surgeries_as_lead",
    )
    anaesthetist = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="surgeries_as_anaesthetist",
    )
    procedure_name = models.CharField(max_length=200)
    icd10_code = models.CharField(max_length=20, blank=True)
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.ELECTIVE
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SCHEDULED
    )
    pre_op_notes = models.TextField(blank=True)
    post_op_notes = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    booked_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="+"
    )

    def __str__(self):
        return (
            f"{self.procedure_name} — {self.patient.full_name} "
            f"({self.scheduled_date})"
        )

    class Meta:
        ordering = ["scheduled_date", "scheduled_time"]
        indexes = [
            models.Index(fields=["scheduled_date", "theatre"]),
            models.Index(fields=["patient", "status"]),
        ]


class SurgeryTeamMember(BaseModel):
    """Additional team members for a surgery (scrub nurses, assistants, etc.)."""

    booking = models.ForeignKey(
        SurgeryBooking, on_delete=models.CASCADE, related_name="team"
    )
    user = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    role = models.CharField(max_length=60)

    class Meta:
        unique_together = [("booking", "user")]
