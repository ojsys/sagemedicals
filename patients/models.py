from django.db import models

from core.models import BaseModel
from patients.constants import (
    ALLERGY_TYPES,
    BLOOD_GROUPS,
    MARITAL_STATUS,
    NIGERIAN_STATES,
    NOK_RELATIONSHIPS,
    PAYER_TYPES,
    PROBLEM_STATUS,
    RELIGIONS,
    SEVERITY_LEVELS,
)


class HospitalNumberSequence(models.Model):
    """Per-year counter used to generate SAGE/YYYY/NNNNNN hospital numbers."""

    year = models.PositiveIntegerField(unique=True)
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Hospital Number Sequence"


class Patient(BaseModel):
    class Sex(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"
        OTHER = "O", "Other / Intersex"

    # Identity
    hospital_number = models.CharField(max_length=32, unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    sex = models.CharField(max_length=1, choices=Sex.choices)
    gender_identity = models.CharField(max_length=100, blank=True)
    marital_status = models.CharField(max_length=20, choices=MARITAL_STATUS, blank=True)
    occupation = models.CharField(max_length=150, blank=True)
    religion = models.CharField(max_length=50, choices=RELIGIONS, blank=True)
    ethnicity = models.CharField(max_length=100, blank=True)
    state_of_origin = models.CharField(max_length=50, choices=NIGERIAN_STATES, blank=True)
    lga_of_origin = models.CharField(max_length=100, blank=True)
    preferred_language = models.CharField(max_length=50, default="English")
    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUPS, blank=True)

    # Contact
    phone = models.CharField(max_length=20)
    phone_alt = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    address_state = models.CharField(max_length=50, choices=NIGERIAN_STATES, blank=True)
    address_lga = models.CharField(max_length=100, blank=True)

    # Payer
    payer_type = models.CharField(max_length=20, choices=PAYER_TYPES, default="self_pay")
    nhia_number = models.CharField(max_length=50, blank=True, db_index=True)
    hmo_name = models.CharField(max_length=150, blank=True)
    hmo_number = models.CharField(max_length=50, blank=True, verbose_name="HMO Member Number")
    hmo_plan = models.CharField(max_length=150, blank=True)
    corporate_employer = models.CharField(max_length=150, blank=True)

    # Media
    photo = models.ImageField(upload_to="patients/photos/", null=True, blank=True)
    id_document = models.FileField(upload_to="patients/documents/", null=True, blank=True, verbose_name="ID Document")
    hmo_card = models.FileField(upload_to="patients/documents/", null=True, blank=True, verbose_name="HMO Card")

    # Portal account (set when patient self-registers on portal)
    user = models.OneToOneField(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="patient_profile",
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["last_name", "first_name"]),
            models.Index(fields=["phone"]),
            models.Index(fields=["date_of_birth"]),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.hospital_number})"

    @property
    def full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p)

    @property
    def age(self):
        from django.utils import timezone
        today = timezone.localdate()
        dob = self.date_of_birth
        years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return years

    @property
    def age_display(self):
        a = self.age
        if a == 0:
            from django.utils import timezone
            today = timezone.localdate()
            months = (today.year - self.date_of_birth.year) * 12 + (today.month - self.date_of_birth.month)
            return f"{months}m"
        return f"{a}y"

    @property
    def active_allergies(self):
        return self.allergies.filter(is_active=True)

    @property
    def has_critical_allergies(self):
        return self.allergies.filter(is_active=True, severity__in=["severe", "life_threatening"]).exists()


class NextOfKin(BaseModel):
    patient = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name="next_of_kin")
    full_name = models.CharField(max_length=200)
    relationship = models.CharField(max_length=30, choices=NOK_RELATIONSHIPS, blank=True)
    phone = models.CharField(max_length=20)
    phone_alt = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return f"{self.full_name} ({self.relationship}) — {self.patient}"


class Allergy(BaseModel):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="allergies")
    allergen = models.CharField(max_length=200)
    allergy_type = models.CharField(max_length=20, choices=ALLERGY_TYPES, default="drug")
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default="moderate")
    reaction = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    date_recorded = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-severity", "allergen"]
        verbose_name_plural = "allergies"
        indexes = [models.Index(fields=["patient", "is_active"])]

    def __str__(self):
        return f"{self.allergen} ({self.get_severity_display()}) — {self.patient}"


class ChronicCondition(BaseModel):
    """Patient problem list entry."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="chronic_conditions")
    icd10_code = models.CharField(max_length=20, blank=True)
    description = models.CharField(max_length=300)
    status = models.CharField(max_length=20, choices=PROBLEM_STATUS, default="active")
    onset_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["status", "description"]

    def __str__(self):
        return f"{self.description} [{self.get_status_display()}] — {self.patient}"
