from datetime import date, timedelta

from django.db import models

from core.models import BaseModel


class ANCRecord(BaseModel):
    """One record per pregnancy for a patient."""

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="anc_records",
    )
    lmp = models.DateField(
        "Last menstrual period",
        null=True, blank=True,
        help_text="Used to calculate gestational age. If unknown, EDD is used.",
    )
    edd = models.DateField("Expected delivery date")
    gravida = models.PositiveSmallIntegerField(
        default=1,
        help_text="Total pregnancies including current",
    )
    para = models.PositiveSmallIntegerField(
        default=0,
        help_text="Previous deliveries at ≥24 weeks",
    )
    blood_group = models.CharField(max_length=5, blank=True)
    rhesus = models.CharField(
        max_length=4, blank=True,
        choices=[("Pos", "+ve"), ("Neg", "-ve")],
    )
    booking_date = models.DateField("Booking date", default=date.today)
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck when pregnancy is concluded (delivery or loss).",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-edd"]
        verbose_name = "ANC Record"
        verbose_name_plural = "ANC Records"

    def __str__(self):
        return f"{self.patient.full_name} — EDD {self.edd}"

    # ── Computed props ──────────────────────────────────────────────

    def _ref_date(self):
        return self.lmp if self.lmp else (self.edd - timedelta(days=280))

    @property
    def gestational_age_weeks(self):
        days = (date.today() - self._ref_date()).days
        return max(0, min(days // 7, 45))

    @property
    def gestational_age_days(self):
        days = (date.today() - self._ref_date()).days
        return max(0, days) % 7

    @property
    def weeks_to_edd(self):
        return max(0, (self.edd - date.today()).days // 7)

    @property
    def progress_pct(self):
        """Percentage through a 40-week pregnancy (clamped 0–100)."""
        return min(100, round(self.gestational_age_weeks / 40 * 100))


class ANCVisit(BaseModel):
    """A single antenatal clinic visit."""

    URINE_PROTEIN = [
        ("neg", "Negative"), ("trace", "Trace"),
        ("+", "+"), ("++", "++"), ("+++", "+++"),
    ]
    URINE_GLUCOSE = [
        ("neg", "Negative"), ("trace", "Trace"),
        ("+", "+"), ("++", "++"),
    ]

    record = models.ForeignKey(
        ANCRecord,
        on_delete=models.CASCADE,
        related_name="visits",
    )
    visit_date = models.DateField()
    gestational_age_weeks = models.PositiveSmallIntegerField("Gestational age (weeks)")
    weight_kg = models.DecimalField(
        "Weight (kg)", max_digits=5, decimal_places=1,
        null=True, blank=True,
    )
    bp_systolic = models.PositiveSmallIntegerField("Systolic BP (mmHg)", null=True, blank=True)
    bp_diastolic = models.PositiveSmallIntegerField("Diastolic BP (mmHg)", null=True, blank=True)
    fundal_height_cm = models.PositiveSmallIntegerField("Fundal height (cm)", null=True, blank=True)
    fetal_heart_rate = models.PositiveSmallIntegerField("Fetal heart rate (bpm)", null=True, blank=True)
    presentation = models.CharField(max_length=40, blank=True)
    urine_protein = models.CharField(max_length=10, blank=True, choices=URINE_PROTEIN)
    urine_glucose = models.CharField(max_length=10, blank=True, choices=URINE_GLUCOSE)
    next_visit_date = models.DateField(null=True, blank=True)
    diagnosis = models.TextField("Diagnosis", blank=True)
    plan = models.TextField("Management plan", blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-visit_date"]
        verbose_name = "ANC Visit"
        verbose_name_plural = "ANC Visits"

    def __str__(self):
        return f"Visit {self.visit_date} — {self.gestational_age_weeks}wks"

    @property
    def bp_display(self):
        if self.bp_systolic and self.bp_diastolic:
            return f"{self.bp_systolic}/{self.bp_diastolic}"
        return "—"


class ObstetricScan(BaseModel):
    """Ultrasound scan report linked to an ANC pregnancy record."""

    AMNIOTIC_FLUID_CHOICES = [
        ("normal", "Normal"),
        ("oligohydramnios", "Oligohydramnios"),
        ("polyhydramnios", "Polyhydramnios"),
    ]
    PLACENTA_CHOICES = [
        ("anterior", "Anterior"),
        ("posterior", "Posterior"),
        ("fundal", "Fundal"),
        ("lateral", "Lateral"),
        ("previa", "Placenta Praevia"),
    ]

    record = models.ForeignKey(
        ANCRecord,
        on_delete=models.CASCADE,
        related_name="scans",
    )
    scan_date = models.DateField("Scan date")
    gestational_age_weeks = models.PositiveSmallIntegerField(
        "GA at scan (weeks)", null=True, blank=True,
    )
    gestational_age_days = models.PositiveSmallIntegerField(
        "GA at scan (days)", null=True, blank=True,
    )
    placenta_location = models.CharField(
        max_length=20, blank=True, choices=PLACENTA_CHOICES,
    )
    amniotic_fluid = models.CharField(
        max_length=20, blank=True, choices=AMNIOTIC_FLUID_CHOICES,
    )
    findings = models.TextField("Findings", blank=True)
    impression = models.TextField("Impression / conclusion", blank=True)
    report_file = models.FileField(
        "Scan report (PDF/image)", upload_to="antenatal/scans/",
        null=True, blank=True,
    )

    class Meta:
        ordering = ["-scan_date"]
        verbose_name = "Obstetric Scan"
        verbose_name_plural = "Obstetric Scans"

    def __str__(self):
        ga = f"{self.gestational_age_weeks}wks" if self.gestational_age_weeks else ""
        return f"Scan {self.scan_date} {ga}".strip()

    @property
    def ga_display(self):
        if self.gestational_age_weeks is not None:
            days = self.gestational_age_days or 0
            return f"{self.gestational_age_weeks}+{days} wks"
        return "—"
