from django.conf import settings
from django.db import models

from core.models import BaseModel


class Clinic(BaseModel):
    name = models.CharField(max_length=150)
    department = models.CharField(max_length=150, blank=True)
    location = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ClinicSchedule(BaseModel):
    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE, related_name="schedules")
    consultant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="clinic_schedules"
    )
    working_days = models.JSONField(default=list)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_duration_minutes = models.PositiveSmallIntegerField(default=15)
    max_per_slot = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.clinic} — {self.consultant.get_full_name()}"

    def slots_for_date(self, date):
        from datetime import datetime, timedelta
        if date.weekday() not in self.working_days:
            return []
        if BlackoutDate.objects.filter(schedule=self, date=date).exists():
            return []
        slots = []
        current = datetime.combine(date, self.start_time)
        end = datetime.combine(date, self.end_time)
        delta = timedelta(minutes=self.slot_duration_minutes)
        while current < end:
            booked = Appointment.objects.filter(
                schedule=self, date=date, slot_time=current.time(),
                status__in=[Appointment.Status.SCHEDULED, Appointment.Status.CHECKED_IN]
            ).count()
            slots.append((current.time(), max(0, self.max_per_slot - booked)))
            current += delta
        return slots


class BlackoutDate(BaseModel):
    schedule = models.ForeignKey(ClinicSchedule, on_delete=models.CASCADE, related_name="blackouts")
    date = models.DateField(db_index=True)
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = [("schedule", "date")]


class Appointment(BaseModel):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        CHECKED_IN = "checked_in", "Checked In"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No Show"

    class AppointmentType(models.TextChoices):
        NEW = "new", "New Patient"
        FOLLOWUP = "followup", "Follow-up"
        PROCEDURE = "procedure", "Procedure"
        REVIEW = "review", "Review"

    class Priority(models.TextChoices):
        NORMAL = "normal", "Normal"
        ELDERLY = "elderly", "Elderly / Frail"
        PREGNANT = "pregnant", "Pregnant"
        EMERGENCY = "emergency", "Emergency"

    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="appointments")
    schedule = models.ForeignKey(ClinicSchedule, on_delete=models.PROTECT, related_name="appointments")
    consultant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="appointments"
    )
    clinic = models.ForeignKey(Clinic, on_delete=models.PROTECT, related_name="appointments")
    date = models.DateField(db_index=True)
    slot_time = models.TimeField()
    appointment_type = models.CharField(max_length=20, choices=AppointmentType.choices, default=AppointmentType.NEW)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    reason_for_visit = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    booked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="booked_appointments"
    )
    sms_reminder_sent = models.BooleanField(default=False)
    email_reminder_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ["date", "slot_time"]
        indexes = [
            models.Index(fields=["date", "status"]),
            models.Index(fields=["consultant", "date"]),
            models.Index(fields=["patient", "date"]),
        ]

    def __str__(self):
        return f"{self.patient} — {self.date} {self.slot_time} ({self.clinic})"


class QueueEntry(BaseModel):
    class TriageLevel(models.TextChoices):
        RED = "red", "Red — Immediate"
        YELLOW = "yellow", "Yellow — Urgent"
        GREEN = "green", "Green — Non-Urgent"

    class QueueStatus(models.TextChoices):
        WAITING = "waiting", "Waiting"
        WITH_DOCTOR = "with_doctor", "With Doctor"
        COMPLETED = "completed", "Completed"
        TRANSFERRED = "transferred", "Transferred"

    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="queue_entries")
    appointment = models.OneToOneField(
        Appointment, null=True, blank=True, on_delete=models.SET_NULL, related_name="queue_entry"
    )
    clinic = models.ForeignKey(Clinic, on_delete=models.PROTECT, related_name="queue_entries")
    date = models.DateField(db_index=True)
    arrived_at = models.DateTimeField(auto_now_add=True)
    triage_level = models.CharField(max_length=10, choices=TriageLevel.choices, default=TriageLevel.GREEN)
    triage_nurse = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="triage_entries"
    )
    triage_time = models.DateTimeField(null=True, blank=True)
    triage_notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=QueueStatus.choices, default=QueueStatus.WAITING)
    is_walk_in = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["date", "clinic", "status"])]

    def __str__(self):
        return f"{self.patient} — {self.date} [{self.get_triage_level_display()}]"
