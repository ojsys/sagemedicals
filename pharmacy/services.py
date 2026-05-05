from django.db import transaction
from django.utils import timezone


def get_fefo_batches(drug, store, quantity_needed):
    """
    Return ordered list of (DrugBatch, qty_to_take) using FEFO logic.
    Raises ValueError if insufficient stock exists.
    """
    from pharmacy.models import DrugBatch

    today = timezone.localdate()
    batches = DrugBatch.objects.filter(
        drug=drug,
        store=store,
        quantity_remaining__gt=0,
        expiry_date__gt=today,
        is_quarantined=False,
    ).order_by("expiry_date")

    plan = []
    remaining = quantity_needed
    for batch in batches:
        if remaining <= 0:
            break
        take = min(batch.quantity_remaining, remaining)
        plan.append((batch, take))
        remaining -= take

    if remaining > 0:
        raise ValueError(
            f"Insufficient stock for {drug}: need {quantity_needed}, "
            f"shortfall {remaining}."
        )
    return plan


@transaction.atomic
def dispense_prescription(prescription, store, dispensed_by):
    """
    Dispense a prescription using FEFO batch draws.
    Updates batch quantities, StockLevel, prescription status, and invoice unit price.
    Returns the Dispense instance.
    """
    from billing.services import add_invoice_item
    from pharmacy.models import Dispense, DispenseLine, StockLevel

    if hasattr(prescription, "dispense"):
        raise ValueError("Prescription already dispensed.")

    plan = get_fefo_batches(prescription.drug, store, prescription.quantity)

    dispense = Dispense.objects.create(
        prescription=prescription,
        store=store,
        dispensed_by=dispensed_by,
        dispensed_at=timezone.now(),
        status=Dispense.Status.DISPENSED,
    )

    unit_cost = None
    for batch, qty in plan:
        DispenseLine.objects.create(dispense=dispense, batch=batch, quantity=qty)
        if unit_cost is None:
            unit_cost = batch.unit_cost
        batch.quantity_remaining -= qty
        batch.save(update_fields=["quantity_remaining"])

    _sync_stock_level(prescription.drug, store)

    prescription.status = "dispensed"
    prescription._current_user = dispensed_by
    prescription.save(update_fields=["status"])

    # Update invoice line with actual dispensed cost
    if unit_cost is not None:
        encounter = prescription.encounter
        from billing.models import InvoiceItem
        item = InvoiceItem.objects.filter(
            invoice__encounter=encounter,
            description__startswith=str(prescription.drug),
        ).first()
        if item:
            item.unit_price = unit_cost
            item.save()
            item.invoice.recalculate()

    return dispense


@transaction.atomic
def receive_goods(receipt):
    """
    Finalise a GoodsReceipt: create DrugBatch rows and update StockLevel for each line.
    Returns the updated receipt.
    """
    from pharmacy.models import DrugBatch, GoodsReceipt

    if receipt.status == GoodsReceipt.Status.RECEIVED:
        raise ValueError("Receipt already finalised.")

    for line in receipt.lines.select_related("drug").all():
        if line.quantity_received == 0:
            continue
        batch, created = DrugBatch.objects.get_or_create(
            drug=line.drug,
            store=receipt.store,
            batch_number=line.batch_number,
            defaults={
                "expiry_date": line.expiry_date,
                "quantity_received": line.quantity_received,
                "quantity_remaining": line.quantity_received,
                "unit_cost": line.unit_cost,
                "supplier": receipt.supplier,
                "received_at": timezone.now(),
                "received_by": receipt.received_by,
            },
        )
        if not created:
            batch.quantity_remaining += line.quantity_received
            batch.quantity_received += line.quantity_received
            batch.save(update_fields=["quantity_remaining", "quantity_received"])

        _sync_stock_level(line.drug, receipt.store)

    receipt.status = GoodsReceipt.Status.RECEIVED
    receipt.save(update_fields=["status"])
    return receipt


def _sync_stock_level(drug, store):
    """Recalculate StockLevel.quantity_on_hand from live batch totals."""
    from django.db.models import Sum

    from pharmacy.models import DrugBatch, StockLevel

    total = (
        DrugBatch.objects.filter(drug=drug, store=store, is_quarantined=False)
        .aggregate(total=Sum("quantity_remaining"))["total"]
        or 0
    )
    StockLevel.objects.update_or_create(
        drug=drug, store=store, defaults={"quantity_on_hand": total}
    )


def get_expiry_alerts(store, days_ahead=90):
    """Return batches expiring within days_ahead that still have stock."""
    from datetime import timedelta

    from pharmacy.models import DrugBatch

    cutoff = timezone.localdate() + timedelta(days=days_ahead)
    return DrugBatch.objects.filter(
        store=store,
        quantity_remaining__gt=0,
        expiry_date__lte=cutoff,
        is_quarantined=False,
    ).select_related("drug").order_by("expiry_date")


def get_low_stock_alerts(store):
    """Return StockLevel rows at or below reorder_level."""
    from django.db.models import F

    from pharmacy.models import StockLevel

    return StockLevel.objects.filter(
        store=store,
        quantity_on_hand__lte=F("reorder_level"),
        reorder_level__gt=0,
    ).select_related("drug")
