from django.db import transaction
from django.utils import timezone


@transaction.atomic
def build_claim_batch(payer, period_start, period_end, submitted_by=None):
    """
    Build a draft ClaimBatch from all paid/partial invoices for a payer's
    patient type in the given period that don't already have a claim.
    Returns (ClaimBatch, list[Claim]).
    """
    from billing.models import Invoice
    from integrations.models import Claim, ClaimBatch

    payer_type_map = {
        "nhia": "nhia",
        "hmo": "private_hmo",
        "employer": "employer",
    }
    patient_payer_type = payer_type_map.get(payer.payer_type)

    batch = ClaimBatch.objects.create(
        payer=payer,
        period_start=period_start,
        period_end=period_end,
        status=ClaimBatch.Status.DRAFT,
    )

    already_claimed_invoice_ids = set(
        Claim.objects.filter(batch__payer=payer).values_list("invoice_id", flat=True)
    )

    invoices = Invoice.objects.filter(
        patient__payer_type=patient_payer_type,
        status__in=[Invoice.Status.PAID, Invoice.Status.PARTIAL],
        created_at__date__gte=period_start,
        created_at__date__lte=period_end,
    ).exclude(pk__in=already_claimed_invoice_ids).select_related("patient")

    claims = []
    for invoice in invoices:
        claim = Claim.objects.create(
            batch=batch,
            invoice=invoice,
            patient=invoice.patient,
            claimed_amount=invoice.total,
        )
        claims.append(claim)

    batch.recalculate_total()
    return batch, claims


@transaction.atomic
def submit_batch(batch, submitted_by):
    """Mark a draft batch as submitted."""
    from integrations.models import ClaimBatch

    if batch.status != ClaimBatch.Status.DRAFT:
        raise ValueError("Only draft batches can be submitted.")
    batch.status = ClaimBatch.Status.SUBMITTED
    batch.submitted_at = timezone.now()
    batch.submitted_by = submitted_by
    batch.save(update_fields=["status", "submitted_at", "submitted_by"])
    return batch


@transaction.atomic
def record_payer_response(batch, approved_claims, rejected_claims, notes=""):
    """
    Process a payer response.
    approved_claims: list of (claim_pk, approved_amount)
    rejected_claims: list of (claim_pk, reason)
    Updates individual claim statuses and batch total_approved.
    """
    from integrations.models import Claim, ClaimBatch

    for claim_pk, amount in approved_claims:
        Claim.objects.filter(pk=claim_pk, batch=batch).update(
            status=Claim.Status.APPROVED,
            approved_amount=amount,
        )

    for claim_pk, reason in rejected_claims:
        Claim.objects.filter(pk=claim_pk, batch=batch).update(
            status=Claim.Status.REJECTED,
            rejection_reason=reason,
        )

    from django.db.models import Sum
    total_approved = (
        batch.claims.filter(status=Claim.Status.APPROVED)
        .aggregate(t=Sum("approved_amount"))["t"] or 0
    )
    batch.total_approved = total_approved
    batch.notes = notes
    batch.status = ClaimBatch.Status.APPROVED
    batch.save(update_fields=["total_approved", "notes", "status"])
    return batch
