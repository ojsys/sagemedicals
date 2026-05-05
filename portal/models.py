"""
Patient-facing portal models.
Portal sessions are phone-OTP authenticated — no Django user account required.
"""
import secrets

from django.db import models
from django.utils import timezone

from core.models import BaseModel


def _token():
    return secrets.token_urlsafe(32)


class PortalSession(BaseModel):
    """
    Authenticated portal session for a patient.
    Created after successful OTP verification; expires after inactivity.
    """

    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE, related_name="portal_sessions"
    )
    token = models.CharField(max_length=64, unique=True, default=_token)
    expires_at = models.DateTimeField()
    last_active = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PortalSession {self.patient} expires {self.expires_at}"

    @property
    def is_valid(self):
        return self.expires_at > timezone.now()

    def touch(self):
        from django.conf import settings
        ttl = getattr(settings, "PATIENT_PORTAL_SESSION_AGE", 3600)
        self.last_active = timezone.now()
        self.expires_at = timezone.now() + timezone.timedelta(seconds=ttl)
        self.save(update_fields=["last_active", "expires_at"])


class PortalAppointmentRequest(BaseModel):
    """
    Patient self-requested appointment — goes to scheduling for confirmation.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        BOOKED = "booked", "Booked"
        DECLINED = "declined", "Declined"

    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE,
        related_name="portal_appointment_requests",
    )
    preferred_date = models.DateField()
    preferred_time = models.TimeField(null=True, blank=True)
    clinic = models.ForeignKey(
        "scheduling.Clinic", on_delete=models.SET_NULL, null=True, blank=True
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    reviewed_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )
    resulting_appointment = models.OneToOneField(
        "scheduling.Appointment", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="portal_request",
    )
    decline_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"PortalRequest — {self.patient} on {self.preferred_date} "
            f"[{self.get_status_display()}]"
        )


class PortalFeedback(BaseModel):
    """Patient satisfaction feedback after an encounter."""

    class Rating(models.IntegerChoices):
        VERY_POOR = 1, "Very Poor"
        POOR = 2, "Poor"
        FAIR = 3, "Fair"
        GOOD = 4, "Good"
        EXCELLENT = 5, "Excellent"

    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE, related_name="feedback"
    )
    encounter = models.OneToOneField(
        "encounters.Encounter", on_delete=models.CASCADE,
        related_name="feedback", null=True, blank=True,
    )
    rating = models.PositiveSmallIntegerField(choices=Rating.choices)
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
