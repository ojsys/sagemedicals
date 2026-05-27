from django.db import migrations
from django.db.models import Sum


def backfill_amount_paid(apps, schema_editor):
    """
    Repair invoices whose payments were recorded but whose denormalized
    ``amount_paid`` was never persisted (recalculate() previously excluded it
    from update_fields). Only touches invoices that actually have payments, so
    directly-set values (e.g. seeded data) without Payment rows are left alone.
    """
    Invoice = apps.get_model("billing", "Invoice")
    for invoice in Invoice.objects.all():
        paid = invoice.payments.aggregate(s=Sum("amount"))["s"]
        if paid is None:
            continue  # no payments → nothing to reconcile
        new_balance = max(0, invoice.total - paid)
        if invoice.amount_paid != paid or invoice.balance != new_balance:
            invoice.amount_paid = paid
            invoice.balance = new_balance
            invoice.save(update_fields=["amount_paid", "balance"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0004_invoice_notes"),
    ]

    operations = [
        migrations.RunPython(backfill_amount_paid, noop),
    ]
