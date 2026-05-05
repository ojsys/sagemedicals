from django.conf import settings
from django.db import models

from core.models import BaseModel


class Encounter(BaseModel):
    class EncounterType(models.TextChoices):
        OPD = "opd", "Outpatient (OPD)"
        AE = "ae", "Accident & Emergency"
        IPD_ROUND = "ipd_round", "Inpatient Ward Round"
        PROCEDURE = "procedure", "Procedure"
        TELEMEDICINE = "telemedicine", "Telemedicine"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SIGNED = "signed", "Signed"
        LOCKED = "locked", "Locked"

    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="encounters")
    encounter_type = models.CharField(max_length=20, choices=EncounterType.choices, default=EncounterType.OPD)
    date_time = models.DateTimeField()
    location = models.CharField(max_length=150, blank=True)
    attending = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="encounters")
    appointment = models.OneToOneField(
        "scheduling.QueueEntry", null=True, blank=True, on_delete=models.SET_NULL, related_name="encounter"
    )
    chief_complaint = models.TextField(blank=True)
    history_of_presenting_illness = models.TextField(blank=True)
    review_of_systems = models.TextField(blank=True)
    examination_findings = models.TextField(blank=True)
    assessment = models.TextField(blank=True)
    plan = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="signed_encounters"
    )
    cosigned_at = models.DateTimeField(null=True, blank=True)
    cosigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="cosigned_encounters"
    )

    class Meta:
        ordering = ["-date_time"]
        indexes = [
            models.Index(fields=["patient", "date_time"]),
            models.Index(fields=["attending", "date_time"]),
        ]

    def __str__(self):
        return f"{self.get_encounter_type_display()} — {self.patient} @ {self.date_time:%d %b %Y %H:%M}"


class Vitals(BaseModel):
    encounter = models.OneToOneField(Encounter, on_delete=models.CASCADE, related_name="vitals")
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    bp_systolic = models.PositiveSmallIntegerField(null=True, blank=True)
    bp_diastolic = models.PositiveSmallIntegerField(null=True, blank=True)
    pulse = models.PositiveSmallIntegerField(null=True, blank=True)
    respiratory_rate = models.PositiveSmallIntegerField(null=True, blank=True)
    spo2 = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    weight = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    height = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    pain_score = models.PositiveSmallIntegerField(null=True, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="vitals_recorded"
    )

    @property
    def bmi(self):
        if self.weight and self.height and self.height > 0:
            h_m = float(self.height) / 100
            return round(float(self.weight) / (h_m * h_m), 1)
        return None

    @property
    def bp_display(self):
        if self.bp_systolic and self.bp_diastolic:
            return f"{self.bp_systolic}/{self.bp_diastolic}"
        return "—"


class Diagnosis(BaseModel):
    class DiagnosisType(models.TextChoices):
        PRIMARY = "primary", "Primary"
        SECONDARY = "secondary", "Secondary"
        WORKING = "working", "Working / Provisional"

    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name="diagnoses")
    icd10_code = models.CharField(max_length=20, blank=True, db_index=True)
    description = models.CharField(max_length=300)
    diagnosis_type = models.CharField(max_length=15, choices=DiagnosisType.choices, default=DiagnosisType.PRIMARY)
    clinician = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="diagnoses"
    )

    class Meta:
        ordering = ["diagnosis_type", "id"]
        verbose_name_plural = "diagnoses"

    def __str__(self):
        code = f"[{self.icd10_code}] " if self.icd10_code else ""
        return f"{code}{self.description}"


class EncounterAttachment(BaseModel):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="encounters/attachments/")
    description = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
