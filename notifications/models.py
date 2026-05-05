from django.db import models

from core.models import BaseModel


class NotificationTemplate(BaseModel):
    """Reusable message templates with {{ variable }} placeholders."""

    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"
        BOTH = "both", "SMS + Email"

    class EventType(models.TextChoices):
        APPOINTMENT_REMINDER = "appointment_reminder", "Appointment Reminder"
        APPOINTMENT_BOOKED = "appointment_booked", "Appointment Booked"
        APPOINTMENT_CANCELLED = "appointment_cancelled", "Appointment Cancelled"
        LAB_RESULT_READY = "lab_result_ready", "Lab Result Ready"
        INVOICE_ISSUED = "invoice_issued", "Invoice Issued"
        PAYMENT_RECEIVED = "payment_received", "Payment Received"
        OTP_VERIFY = "otp_verify", "OTP Verification"
        DISCHARGE_SUMMARY = "discharge_summary", "Discharge Summary"
        CUSTOM = "custom", "Custom"

    event_type = models.CharField(
        max_length=40, choices=EventType.choices, unique=True
    )
    channel = models.CharField(
        max_length=10, choices=Channel.choices, default=Channel.SMS
    )
    subject = models.CharField(max_length=200, blank=True, help_text="Email subject")
    body_sms = models.TextField(blank=True, help_text="SMS body (160 chars per segment)")
    body_email = models.TextField(blank=True, help_text="Plain-text email body")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.get_event_type_display()} [{self.get_channel_display()}]"

    class Meta:
        ordering = ["event_type"]


class Notification(BaseModel):
    """A single dispatched notification — one row per channel attempt."""

    class Channel(models.TextChoices):
        SMS = "sms", "SMS"
        EMAIL = "email", "Email"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        BOUNCED = "bounced", "Bounced"

    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.CASCADE,
        related_name="notifications", null=True, blank=True,
    )
    channel = models.CharField(max_length=10, choices=Channel.choices)
    recipient = models.CharField(max_length=200)
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.QUEUED
    )
    provider_reference = models.CharField(max_length=120, blank=True)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    event_type = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["patient", "status"]),
            models.Index(fields=["event_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.get_channel_display()} to {self.recipient} [{self.get_status_display()}]"


class OTPVerification(BaseModel):
    """One-time passcode for patient portal phone verification."""

    phone = models.CharField(max_length=20)
    code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["phone", "is_used"])]

    def __str__(self):
        return f"OTP {self.phone} [{'used' if self.is_used else 'active'}]"
