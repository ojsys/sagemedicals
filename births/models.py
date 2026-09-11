from django.conf import settings
from django.db import models

from antenatal.models import ANCRecord
from core.models import BaseModel
from patients.models import Patient


class BirthCertificateSequence(models.Model):
    """Per-year counter used to generate SAGE/BC/YYYY/NNNNN certificate numbers."""

    year = models.PositiveIntegerField(unique=True)
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Birth Certificate Sequence"


class BirthRecord(BaseModel):
    """A live birth at the hospital — one record per baby, printed as a birth certificate."""

    MULTIPLE_BIRTH_NAMES = {2: "Twin", 3: "Triplet", 4: "Quadruplet"}

    certificate_number = models.CharField(max_length=32, unique=True, editable=False)
    mother = models.ForeignKey(
        "patients.Patient",
        on_delete=models.PROTECT,
        related_name="birth_records",
    )
    anc_record = models.ForeignKey(
        "antenatal.ANCRecord",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="birth_records",
        verbose_name="ANC record",
    )

    # ── Child ────────────────────────────────────────────────────────
    child_first_name = models.CharField("Child's first name", max_length=100)
    child_middle_name = models.CharField("Child's middle name", max_length=100, blank=True)
    child_surname = models.CharField("Child's surname", max_length=100)
    sex = models.CharField(max_length=1, choices=Patient.Sex.choices)

    # ── Birth details ────────────────────────────────────────────────
    date_of_birth = models.DateField("Date of birth")
    time_of_birth = models.TimeField("Time of birth")
    weight_kg = models.DecimalField("Birth weight (kg)", max_digits=4, decimal_places=2)
    length_cm = models.DecimalField(
        "Length (cm)", max_digits=4, decimal_places=1, null=True, blank=True,
    )
    gestational_age_weeks = models.PositiveSmallIntegerField(
        "Gestation at birth (weeks)", null=True, blank=True,
    )
    delivery_mode = models.CharField(
        "Mode of delivery",
        max_length=20, blank=True, choices=ANCRecord.DELIVERY_MODE_CHOICES,
    )
    birth_order = models.PositiveSmallIntegerField(
        "Birth order", default=1,
        help_text="1 for the first-born, 2 for the second twin, etc.",
    )
    babies_in_delivery = models.PositiveSmallIntegerField(
        "Babies in this delivery", default=1,
        help_text="1 for a singleton, 2 for twins.",
    )

    # ── Parents & attendant ──────────────────────────────────────────
    father_name = models.CharField("Father's full name", max_length=200, blank=True)
    attended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
        verbose_name="Attending clinician / midwife",
    )
    notes = models.TextField(
        "Internal notes", blank=True,
        help_text="For the file only — not printed on the certificate.",
    )

    class Meta:
        ordering = ["-date_of_birth", "-time_of_birth"]
        verbose_name = "Birth Record"
        verbose_name_plural = "Birth Register"

    def __str__(self):
        return f"{self.certificate_number} — {self.child_full_name}"

    def save(self, *args, **kwargs):
        if not self.certificate_number:
            from births.services import generate_certificate_number
            self.certificate_number = generate_certificate_number()
        super().save(*args, **kwargs)

    @property
    def child_full_name(self):
        parts = [self.child_first_name, self.child_middle_name, self.child_surname]
        return " ".join(p for p in parts if p)

    @property
    def birth_type_display(self):
        """'Singleton', or e.g. 'Twin 2 of 2' for multiple births."""
        count = self.babies_in_delivery or 1
        if count <= 1:
            return "Singleton"
        kind = self.MULTIPLE_BIRTH_NAMES.get(count, "Multiple")
        return f"{kind} {self.birth_order} of {count}"
