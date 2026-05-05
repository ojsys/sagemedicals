from django.db import models
from django.utils import timezone

from core.models import BaseModel


class Ward(BaseModel):
    name = models.CharField(max_length=120)
    ward_type = models.CharField(max_length=40, blank=True)
    floor = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    consultant = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="wards",
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]


class Room(BaseModel):
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=40)
    is_isolation = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.ward} / {self.name}"

    class Meta:
        unique_together = [("ward", "name")]
        ordering = ["ward", "name"]


class Bed(BaseModel):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        OCCUPIED = "occupied", "Occupied"
        MAINTENANCE = "maintenance", "Under Maintenance"

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="beds")
    label = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)

    def __str__(self):
        return f"{self.room.ward} / {self.room.name} / Bed {self.label}"

    class Meta:
        unique_together = [("room", "label")]
        ordering = ["room__ward__name", "room__name", "label"]

    @property
    def ward(self):
        return self.room.ward


class Admission(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        TRANSFERRED = "transferred", "Transferred"
        DISCHARGED = "discharged", "Discharged"
        DECEASED = "deceased", "Deceased"

    class DischargeType(models.TextChoices):
        ROUTINE = "routine", "Routine"
        SELF_DISCHARGE = "self_discharge", "Self-discharge (AMA)"
        TRANSFERRED_OUT = "transferred_out", "Transferred Out"
        DECEASED = "deceased", "Deceased"

    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.PROTECT, related_name="admissions"
    )
    bed = models.ForeignKey(Bed, on_delete=models.PROTECT, related_name="admissions")
    admitting_doctor = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True,
        related_name="admissions_as_doctor",
    )
    admitting_encounter = models.OneToOneField(
        "encounters.Encounter", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="admission",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    admitted_at = models.DateTimeField(default=timezone.now)
    diagnosis_on_admission = models.TextField(blank=True)
    discharge_type = models.CharField(
        max_length=30, choices=DischargeType.choices, blank=True
    )
    discharged_at = models.DateTimeField(null=True, blank=True)
    discharge_summary = models.TextField(blank=True)
    discharged_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )

    def __str__(self):
        return (
            f"{self.patient.full_name} — {self.bed} ({self.get_status_display()})"
        )

    class Meta:
        ordering = ["-admitted_at"]
        indexes = [
            models.Index(fields=["patient", "status"]),
            models.Index(fields=["bed", "status"]),
        ]


class BedTransfer(BaseModel):
    """Records every bed move during an admission."""

    admission = models.ForeignKey(
        Admission, on_delete=models.CASCADE, related_name="transfers"
    )
    from_bed = models.ForeignKey(
        Bed, on_delete=models.PROTECT, related_name="+", null=True, blank=True
    )
    to_bed = models.ForeignKey(
        Bed, on_delete=models.PROTECT, related_name="+"
    )
    transferred_at = models.DateTimeField(default=timezone.now)
    transferred_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    reason = models.TextField(blank=True)


class WardRound(BaseModel):
    """Inpatient doctor note / ward round entry."""

    admission = models.ForeignKey(
        Admission, on_delete=models.CASCADE, related_name="ward_rounds"
    )
    clinician = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True,
        related_name="ward_rounds",
    )
    note = models.TextField()
    vitals_note = models.TextField(blank=True)
    plan = models.TextField(blank=True)
    round_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-round_at"]

    def __str__(self):
        return (
            f"Round {self.pk} — {self.admission.patient.full_name} "
            f"{self.round_at:%Y-%m-%d %H:%M}"
        )


class MedicationAdministration(BaseModel):
    """eMAR — single administration event for an inpatient prescription."""

    class Result(models.TextChoices):
        GIVEN = "given", "Given"
        HELD = "held", "Held"
        REFUSED = "refused", "Refused by Patient"
        NOT_AVAILABLE = "not_available", "Not Available"

    admission = models.ForeignKey(
        Admission, on_delete=models.CASCADE, related_name="mar_entries"
    )
    prescription = models.ForeignKey(
        "prescriptions.Prescription", on_delete=models.PROTECT,
        related_name="mar_entries",
    )
    administered_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    scheduled_at = models.DateTimeField()
    administered_at = models.DateTimeField(null=True, blank=True)
    result = models.CharField(
        max_length=20, choices=Result.choices, default=Result.GIVEN
    )
    dose_given = models.CharField(max_length=60, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-scheduled_at"]
        indexes = [models.Index(fields=["admission", "scheduled_at"])]
