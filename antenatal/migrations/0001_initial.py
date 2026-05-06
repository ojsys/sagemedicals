import datetime

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("patients", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ANCRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("lmp", models.DateField(blank=True, help_text="Used to calculate gestational age. If unknown, EDD is used.", null=True, verbose_name="Last menstrual period")),
                ("edd", models.DateField(verbose_name="Expected delivery date")),
                ("gravida", models.PositiveSmallIntegerField(default=1, help_text="Total pregnancies including current")),
                ("para", models.PositiveSmallIntegerField(default=0, help_text="Previous deliveries at ≥24 weeks")),
                ("blood_group", models.CharField(blank=True, max_length=5)),
                ("rhesus", models.CharField(blank=True, choices=[("Pos", "+ve"), ("Neg", "-ve")], max_length=4)),
                ("booking_date", models.DateField(default=datetime.date.today, verbose_name="Booking date")),
                ("is_active", models.BooleanField(default=True, help_text="Uncheck when pregnancy is concluded (delivery or loss).")),
                ("notes", models.TextField(blank=True)),
                ("patient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="anc_records", to="patients.patient")),
            ],
            options={
                "verbose_name": "ANC Record",
                "verbose_name_plural": "ANC Records",
                "ordering": ["-edd"],
            },
        ),
        migrations.CreateModel(
            name="ANCVisit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("visit_date", models.DateField()),
                ("gestational_age_weeks", models.PositiveSmallIntegerField(verbose_name="Gestational age (weeks)")),
                ("weight_kg", models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name="Weight (kg)")),
                ("bp_systolic", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Systolic BP (mmHg)")),
                ("bp_diastolic", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Diastolic BP (mmHg)")),
                ("fundal_height_cm", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Fundal height (cm)")),
                ("fetal_heart_rate", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Fetal heart rate (bpm)")),
                ("presentation", models.CharField(blank=True, max_length=40)),
                ("urine_protein", models.CharField(blank=True, choices=[("neg", "Negative"), ("trace", "Trace"), ("+", "+"), ("++", "++"), ("+++", "+++")], max_length=10)),
                ("urine_glucose", models.CharField(blank=True, choices=[("neg", "Negative"), ("trace", "Trace"), ("+", "+"), ("++", "++")], max_length=10)),
                ("next_visit_date", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("record", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="visits", to="antenatal.ancrecord")),
            ],
            options={
                "verbose_name": "ANC Visit",
                "verbose_name_plural": "ANC Visits",
                "ordering": ["-visit_date"],
            },
        ),
    ]
