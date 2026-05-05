from django.db import transaction
from django.utils import timezone


@transaction.atomic
def admit_patient(patient, bed, admitting_doctor, diagnosis="", encounter=None, user=None):
    """
    Admit a patient to a bed.
    Validates bed is available, marks it occupied, creates Admission + initial BedTransfer.
    Returns the Admission instance.
    """
    from admissions.models import Admission, Bed, BedTransfer

    bed_obj = Bed.objects.select_for_update().get(pk=bed.pk)
    if bed_obj.status != Bed.Status.AVAILABLE:
        raise ValueError(f"Bed {bed_obj.label} is not available (status: {bed_obj.status}).")

    existing = Admission.objects.filter(
        patient=patient, status=Admission.Status.ACTIVE
    ).first()
    if existing:
        raise ValueError(
            f"{patient.full_name} already has an active admission (#{existing.pk})."
        )

    admission = Admission.objects.create(
        patient=patient,
        bed=bed_obj,
        admitting_doctor=admitting_doctor,
        admitting_encounter=encounter,
        diagnosis_on_admission=diagnosis,
        status=Admission.Status.ACTIVE,
    )
    if user:
        admission._current_user = user

    bed_obj.status = Bed.Status.OCCUPIED
    bed_obj.save(update_fields=["status"])

    BedTransfer.objects.create(
        admission=admission,
        from_bed=None,
        to_bed=bed_obj,
        transferred_by=admitting_doctor,
        reason="Initial admission",
    )
    return admission


@transaction.atomic
def transfer_bed(admission, new_bed, transferred_by, reason="", user=None):
    """
    Move an active admission to a different bed.
    Frees the old bed, marks the new one occupied.
    """
    from admissions.models import Admission, Bed, BedTransfer

    if admission.status != Admission.Status.ACTIVE:
        raise ValueError("Can only transfer an active admission.")

    new_bed_obj = Bed.objects.select_for_update().get(pk=new_bed.pk)
    if new_bed_obj.status != Bed.Status.AVAILABLE:
        raise ValueError(f"Bed {new_bed_obj.label} is not available.")

    old_bed = admission.bed
    old_bed.status = Bed.Status.AVAILABLE
    old_bed.save(update_fields=["status"])

    new_bed_obj.status = Bed.Status.OCCUPIED
    new_bed_obj.save(update_fields=["status"])

    BedTransfer.objects.create(
        admission=admission,
        from_bed=old_bed,
        to_bed=new_bed_obj,
        transferred_by=transferred_by,
        reason=reason,
    )

    admission.bed = new_bed_obj
    if user:
        admission._current_user = user
    admission.save(update_fields=["bed"])
    return admission


@transaction.atomic
def discharge_patient(admission, discharge_type, summary="", discharged_by=None, user=None):
    """
    Discharge an active admission.
    Frees the bed, updates status and discharge fields.
    """
    from admissions.models import Admission, Bed

    if admission.status != Admission.Status.ACTIVE:
        raise ValueError("Admission is not active.")

    admission.status = Admission.Status.DISCHARGED
    admission.discharge_type = discharge_type
    admission.discharge_summary = summary
    admission.discharged_at = timezone.now()
    admission.discharged_by = discharged_by
    if user:
        admission._current_user = user
    admission.save()

    bed = Bed.objects.select_for_update().get(pk=admission.bed_id)
    bed.status = Bed.Status.AVAILABLE
    bed.save(update_fields=["status"])

    return admission


def get_ward_bed_map(ward):
    """
    Return a structured bed-map for a ward:
    list of rooms, each with its beds and current admission (if occupied).
    """
    from admissions.models import Admission

    rooms = ward.rooms.prefetch_related("beds").order_by("name")
    occupied = {
        a.bed_id: a
        for a in Admission.objects.filter(
            bed__room__ward=ward, status=Admission.Status.ACTIVE
        ).select_related("patient")
    }

    result = []
    for room in rooms:
        beds = []
        for bed in room.beds.all():
            beds.append({"bed": bed, "admission": occupied.get(bed.pk)})
        result.append({"room": room, "beds": beds})
    return result
