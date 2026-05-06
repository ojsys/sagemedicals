import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("antenatal", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="ancvisit",
            name="diagnosis",
            field=models.TextField(blank=True, verbose_name="Diagnosis"),
        ),
        migrations.AddField(
            model_name="ancvisit",
            name="plan",
            field=models.TextField(blank=True, verbose_name="Management plan"),
        ),
        migrations.CreateModel(
            name="ObstetricScan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("scan_date", models.DateField(verbose_name="Scan date")),
                ("gestational_age_weeks", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="GA at scan (weeks)")),
                ("gestational_age_days", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="GA at scan (days)")),
                ("placenta_location", models.CharField(
                    blank=True, max_length=20,
                    choices=[
                        ("anterior", "Anterior"), ("posterior", "Posterior"),
                        ("fundal", "Fundal"), ("lateral", "Lateral"),
                        ("previa", "Placenta Praevia"),
                    ],
                )),
                ("amniotic_fluid", models.CharField(
                    blank=True, max_length=20,
                    choices=[
                        ("normal", "Normal"),
                        ("oligohydramnios", "Oligohydramnios"),
                        ("polyhydramnios", "Polyhydramnios"),
                    ],
                )),
                ("findings", models.TextField(blank=True, verbose_name="Findings")),
                ("impression", models.TextField(blank=True, verbose_name="Impression / conclusion")),
                ("report_file", models.FileField(blank=True, null=True, upload_to="antenatal/scans/", verbose_name="Scan report (PDF/image)")),
                ("record", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="scans",
                    to="antenatal.ancrecord",
                )),
            ],
            options={
                "verbose_name": "Obstetric Scan",
                "verbose_name_plural": "Obstetric Scans",
                "ordering": ["-scan_date"],
            },
        ),
    ]
