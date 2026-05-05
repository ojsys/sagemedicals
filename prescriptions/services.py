from django.db.models import Q


def check_allergy(patient, drug):
    """Return the matching Allergy if the patient has a documented allergy to this drug, else None."""
    from patients.models import Allergy

    allergen = drug.generic_name.lower()
    brand = drug.brand_name.lower() if drug.brand_name else ""

    return Allergy.objects.filter(
        patient=patient,
        is_active=True,
        allergy_type="drug",
    ).filter(
        Q(allergen__icontains=allergen) | (Q(allergen__icontains=brand) if brand else Q(pk__in=[]))
    ).first()


def check_interactions(drug, active_prescriptions):
    """Return list of (Prescription, DrugInteraction) for interactions with currently active prescriptions."""
    from prescriptions.models import DrugInteraction

    drug_ids = [p.drug_id for p in active_prescriptions]
    interactions = DrugInteraction.objects.filter(
        Q(drug_a=drug, drug_b_id__in=drug_ids) | Q(drug_b=drug, drug_a_id__in=drug_ids)
    ).select_related("drug_a", "drug_b")

    results = []
    for interaction in interactions:
        other_drug = interaction.drug_b if interaction.drug_a_id == drug.pk else interaction.drug_a
        matching_rx = next((p for p in active_prescriptions if p.drug_id == other_drug.pk), None)
        if matching_rx:
            results.append((matching_rx, interaction))
    return results


def get_active_prescriptions(patient, exclude_encounter=None):
    """Return active (pending/partial) prescriptions for a patient."""
    from prescriptions.models import Prescription

    qs = Prescription.objects.filter(
        patient=patient,
        status__in=[Prescription.Status.PENDING, Prescription.Status.PARTIALLY_DISPENSED],
    ).select_related("drug")
    if exclude_encounter:
        qs = qs.exclude(encounter=exclude_encounter)
    return list(qs)


def generate_invoice_number():
    """Generate sequential INV/YYYY/NNNNNN invoice number."""
    from django.db import transaction
    from django.utils import timezone

    from billing.models import Invoice

    year = timezone.localdate().year
    prefix = f"INV/{year}/"
    with transaction.atomic():
        last = Invoice.objects.filter(invoice_number__startswith=prefix).order_by("-invoice_number").first()
        if last:
            seq = int(last.invoice_number.split("/")[2]) + 1
        else:
            seq = 1
        return f"{prefix}{seq:06d}"
