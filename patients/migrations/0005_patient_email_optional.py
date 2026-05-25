from django.db import migrations, models


def clear_placeholder_emails(apps, schema_editor):
    """Migration 0004 backfilled missing emails with patient_<pk>_noemail@example.com
    so the unique-not-null constraint could be applied. Now that email is optional,
    convert those placeholders back to NULL."""
    Patient = apps.get_model("patients", "Patient")
    Patient.objects.using(schema_editor.connection.alias).filter(
        email__endswith="_noemail@example.com"
    ).update(email=None)


class Migration(migrations.Migration):

    dependencies = [
        ("patients", "0003_alter_patient_email_alter_patient_phone"),
    ]

    operations = [
        migrations.AlterField(
            model_name="patient",
            name="email",
            field=models.EmailField(blank=True, max_length=254, null=True, unique=True),
        ),
        migrations.RunPython(clear_placeholder_emails, reverse_code=migrations.RunPython.noop),
    ]
