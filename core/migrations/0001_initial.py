from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SiteSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("hospital_name", models.CharField(default="SAGE Medical Center", help_text="Full legal name, used in page titles, emails, and documents.", max_length=120)),
                ("short_name", models.CharField(default="SAGE", help_text="Abbreviated name shown in the sidebar brand mark (e.g. SAGE).", max_length=30)),
                ("tagline", models.CharField(blank=True, help_text="Sub-label under the brand mark (e.g. 'Medical Center'). Defaults to 'EMR' if blank.", max_length=100)),
                ("logo", models.ImageField(blank=True, help_text="Logo shown in the sidebar and patient portal header. Use a transparent PNG optimised for dark backgrounds (min 300 px wide).", upload_to="site/")),
                ("logo_on_light", models.ImageField(blank=True, help_text="Full-colour logo for invoices, reports, and other printed documents. Leave blank to use the primary logo above.", upload_to="site/", verbose_name="Logo (for light backgrounds)")),
                ("favicon", models.ImageField(blank=True, help_text="Browser tab icon. Recommended: 32\xd732 or 64\xd764 PNG.", upload_to="site/")),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("address", models.TextField(blank=True, help_text="Full mailing / physical address.")),
                ("website", models.URLField(blank=True)),
                ("nhia_code", models.CharField(blank=True, help_text="NHIA facility/provider code printed on insurance claims.", max_length=40, verbose_name="NHIA code")),
                ("accreditation", models.CharField(blank=True, help_text="Accreditation body or certificate number (printed on documents).", max_length=100)),
                ("rc_number", models.CharField(blank=True, help_text="CAC registration number.", max_length=40, verbose_name="RC number")),
                ("footer_note", models.CharField(blank=True, help_text="Short line shown in the footer of invoices and lab reports (e.g. hours, slogan).", max_length=220)),
            ],
            options={
                "verbose_name": "Site Settings",
                "verbose_name_plural": "Site Settings",
            },
        ),
    ]
