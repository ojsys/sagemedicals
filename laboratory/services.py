from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from laboratory.models import LabOrder

# Orders whose sample is never collected are auto-cancelled after this many hours.
LAB_ORDER_EXPIRY_HOURS = getattr(settings, "LAB_ORDER_EXPIRY_HOURS", 48)

EXPIRED_REASON = f"{LabOrder.AUTO_EXPIRED_PREFIX}: sample not collected within {LAB_ORDER_EXPIRY_HOURS} hours of request."


def expiry_cutoff(now=None):
    return (now or timezone.now()) - timedelta(hours=LAB_ORDER_EXPIRY_HOURS)


def remove_lab_invoice_item(order):
    """Best-effort: drop the matching InvoiceItem this lab order added (description-based match)."""
    if not order.encounter_id:
        return
    from billing.models import Invoice, InvoiceItem
    invoices = Invoice.objects.filter(encounter_id=order.encounter_id).exclude(status=Invoice.Status.PAID)
    for inv in invoices:
        item = InvoiceItem.objects.filter(
            invoice=inv, description=f"Lab: {order.test.name}"
        ).order_by("-created_at").first()
        if item:
            item.delete()
            inv.recalculate()
            return


def cancel_order(order, reason, user=None):
    """Cancel a not-yet-released order and remove its unpaid billing line."""
    order.status = LabOrder.Status.CANCELLED
    order.cancel_reason = reason[:200]
    if user is not None:
        order._current_user = user
    order.save(update_fields=["status", "cancel_reason", "updated_at"])
    remove_lab_invoice_item(order)


def expire_stale_orders(now=None):
    """Cancel orders still awaiting sample collection after LAB_ORDER_EXPIRY_HOURS.

    Only untouched orders (status ORDERED) expire — once a sample is collected the
    lab owns it and it stays on the worklist until resulted or cancelled by hand.
    """
    stale = (
        LabOrder.objects.filter(status=LabOrder.Status.ORDERED, created_at__lt=expiry_cutoff(now))
        .select_related("test")
    )
    count = 0
    for order in stale:
        with transaction.atomic():
            cancel_order(order, EXPIRED_REASON)
        count += 1
    return count
