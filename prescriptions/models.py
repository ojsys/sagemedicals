from django.conf import settings
from django.db import models

from core.models import BaseModel


class Drug(BaseModel):
    class Category(models.TextChoices):
        POM = "pom", "Prescription Only (POM)"
        OTC = "otc", "Over the Counter (OTC)"
        CONTROLLED = "controlled", "Controlled Drug"

    class DosageForm(models.TextChoices):
        TABLET = "tablet", "Tablet"
        CAPSULE = "capsule", "Capsule"
        SYRUP = "syrup", "Syrup / Suspension"
        INJECTION = "injection", "Injection"
        CREAM = "cream", "Cream / Ointment"
        DROPS = "drops", "Drops"
        INHALER = "inhaler", "Inhaler"
        PATCH = "patch", "Patch"
        SUPPOSITORY = "suppository", "Suppository"
        OTHER = "other", "Other"

    generic_name = models.CharField(max_length=200, db_index=True)
    brand_name = models.CharField(max_length=200, blank=True)
    strength = models.CharField(max_length=100, blank=True)
    dosage_form = models.CharField(max_length=20, choices=DosageForm.choices, default=DosageForm.TABLET)
    default_route = models.CharField(max_length=50, default="oral")
    category = models.CharField(max_length=15, choices=Category.choices, default=Category.POM)
    atc_code = models.CharField(max_length=20, blank=True)
    nafdac_number = models.CharField(max_length=50, blank=True)
    is_formulary = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    default_frequency = models.CharField(max_length=50, blank=True)
    default_duration_days = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["generic_name", "strength"]
        indexes = [models.Index(fields=["generic_name"]), models.Index(fields=["brand_name"])]

    def __str__(self):
        parts = [self.generic_name]
        if self.strength:
            parts.append(self.strength)
        if self.dosage_form:
            parts.append(self.get_dosage_form_display())
        return " ".join(parts)


class DrugInteraction(BaseModel):
    class Severity(models.TextChoices):
        MILD = "mild", "Mild"
        MODERATE = "moderate", "Moderate"
        SEVERE = "severe", "Severe"
        CONTRAINDICATED = "contraindicated", "Contraindicated"

    drug_a = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name="interactions_as_a")
    drug_b = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name="interactions_as_b")
    severity = models.CharField(max_length=20, choices=Severity.choices)
    description = models.TextField()
    clinical_significance = models.TextField(blank=True)

    class Meta:
        unique_together = [("drug_a", "drug_b")]

    def __str__(self):
        return f"{self.drug_a} ↔ {self.drug_b} [{self.get_severity_display()}]"


ROUTE_CHOICES = [
    ("oral", "Oral"), ("iv", "Intravenous"), ("im", "Intramuscular"),
    ("sc", "Subcutaneous"), ("topical", "Topical"), ("inhaled", "Inhaled"),
    ("sublingual", "Sublingual"), ("rectal", "Rectal"), ("other", "Other"),
]

FREQUENCY_CHOICES = [
    ("od", "Once daily (OD)"), ("bd", "Twice daily (BD)"), ("tds", "Three times daily (TDS)"),
    ("qid", "Four times daily (QID)"), ("qhs", "At bedtime"), ("prn", "As needed (PRN)"),
    ("stat", "Immediately (STAT)"), ("weekly", "Once weekly"), ("other", "Other"),
]


class Prescription(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DISPENSED = "dispensed", "Dispensed"
        PARTIALLY_DISPENSED = "partial", "Partially Dispensed"
        CANCELLED = "cancelled", "Cancelled"
        HELD = "held", "On Hold"

    encounter = models.ForeignKey("encounters.Encounter", on_delete=models.CASCADE, related_name="prescriptions")
    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="prescriptions")
    drug = models.ForeignKey(Drug, on_delete=models.PROTECT, related_name="prescriptions")
    dose = models.CharField(max_length=100)
    route = models.CharField(max_length=20, choices=ROUTE_CHOICES, default="oral")
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="od")
    frequency_other = models.CharField(max_length=100, blank=True)
    duration_days = models.PositiveSmallIntegerField(null=True, blank=True)
    quantity = models.PositiveSmallIntegerField(default=1)
    instructions = models.TextField(blank=True)
    is_prn = models.BooleanField(default=False)
    is_stat = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    prescriber = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="prescriptions"
    )
    # Safety override
    allergy_override_reason = models.TextField(blank=True)
    interaction_override_reason = models.TextField(blank=True)
    # Controlled drug co-sign
    cosigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="cosigned_prescriptions"
    )
    refills_allowed = models.PositiveSmallIntegerField(default=0)
    refills_remaining = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["patient", "status"])]

    def __str__(self):
        return f"{self.drug} — {self.dose} {self.get_frequency_display()} × {self.duration_days}d"
