"""
Reporting services — aggregate queries for dashboards and statutory returns.
All functions accept a date range and return plain dicts or querysets.
"""
from datetime import date, timedelta

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone


# ── Operational dashboard ─────────────────────────────────────

def daily_snapshot(target_date=None):
    """Key operational metrics for a single day (defaults to today)."""
    from admissions.models import Admission
    from billing.models import Invoice, Payment
    from encounters.models import Encounter
    from scheduling.models import QueueEntry

    d = target_date or timezone.localdate()

    return {
        "date": d,
        "outpatients": Encounter.objects.filter(date_time__date=d).count(),
        "queue_waiting": QueueEntry.objects.filter(
            date=d, status=QueueEntry.QueueStatus.WAITING
        ).count(),
        "active_admissions": Admission.objects.filter(
            status=Admission.Status.ACTIVE
        ).count(),
        "admissions_today": Admission.objects.filter(
            admitted_at__date=d
        ).count(),
        "discharges_today": Admission.objects.filter(
            discharged_at__date=d
        ).count(),
        "revenue_today": Payment.objects.filter(
            received_at__date=d
        ).aggregate(t=Sum("amount"))["t"] or 0,
        "invoices_outstanding": Invoice.objects.filter(
            status__in=[Invoice.Status.ISSUED, Invoice.Status.PARTIAL]
        ).aggregate(t=Sum("balance"))["t"] or 0,
    }


def bed_occupancy(ward=None):
    """Current bed occupancy. If ward is None, returns hospital-wide totals."""
    from admissions.models import Admission, Bed

    qs = Bed.objects.all()
    if ward:
        qs = qs.filter(room__ward=ward)

    total = qs.count()
    occupied = qs.filter(status=Bed.Status.OCCUPIED).count()
    maintenance = qs.filter(status=Bed.Status.MAINTENANCE).count()
    available = total - occupied - maintenance

    return {
        "total": total,
        "occupied": occupied,
        "available": available,
        "maintenance": maintenance,
        "occupancy_pct": round(occupied / total * 100, 1) if total else 0,
    }


# ── Financial dashboard ───────────────────────────────────────

def revenue_summary(start: date, end: date):
    """Revenue breakdown by payment mode and payer type over a period."""
    from billing.models import Payment

    by_mode = (
        Payment.objects.filter(received_at__date__gte=start, received_at__date__lte=end)
        .values("mode")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )

    daily = (
        Payment.objects.filter(received_at__date__gte=start, received_at__date__lte=end)
        .annotate(day=TruncDate("received_at"))
        .values("day")
        .annotate(total=Sum("amount"))
        .order_by("day")
    )

    total = (
        Payment.objects.filter(received_at__date__gte=start, received_at__date__lte=end)
        .aggregate(t=Sum("amount"))["t"] or 0
    )

    return {"total": total, "by_mode": list(by_mode), "daily": list(daily)}


def outstanding_invoices(limit=50):
    """Invoices with outstanding balances, oldest first."""
    from billing.models import Invoice

    return (
        Invoice.objects.filter(
            status__in=[Invoice.Status.ISSUED, Invoice.Status.PARTIAL]
        )
        .select_related("patient")
        .order_by("created_at")[:limit]
    )


def revenue_by_service_category(start: date, end: date):
    """Revenue broken down by service catalogue category."""
    from billing.models import InvoiceItem

    return (
        InvoiceItem.objects.filter(
            invoice__created_at__date__gte=start,
            invoice__created_at__date__lte=end,
            invoice__status__in=["paid", "partial"],
        )
        .values("service__category")
        .annotate(total=Sum("total"), count=Count("id"))
        .order_by("-total")
    )


# ── Clinical dashboard ────────────────────────────────────────

def top_diagnoses(start: date, end: date, limit=10):
    """Most frequent ICD-10 codes in encounters over a period."""
    from encounters.models import Diagnosis

    return (
        Diagnosis.objects.filter(
            encounter__date_time__date__gte=start,
            encounter__date_time__date__lte=end,
        )
        .values("icd10_code", "description")
        .annotate(count=Count("id"))
        .order_by("-count")[:limit]
    )


def top_drugs_prescribed(start: date, end: date, limit=10):
    """Most frequently prescribed drugs over a period."""
    from prescriptions.models import Prescription

    return (
        Prescription.objects.filter(
            created_at__date__gte=start,
            created_at__date__lte=end,
        )
        .values("drug__generic_name", "drug__strength")
        .annotate(count=Count("id"))
        .order_by("-count")[:limit]
    )


def lab_turnaround(start: date, end: date):
    """Average hours from order to result release per test type."""
    from laboratory.models import LabOrder

    return (
        LabOrder.objects.filter(
            status=LabOrder.Status.RELEASED,
            created_at__date__gte=start,
            created_at__date__lte=end,
            result__released_at__isnull=False,
        )
        .values("test__name")
        .annotate(count=Count("id"))
        .order_by("test__name")
    )


def encounter_volume(start: date, end: date):
    """Daily encounter counts over a period."""
    from encounters.models import Encounter

    return (
        Encounter.objects.filter(
            date_time__date__gte=start,
            date_time__date__lte=end,
        )
        .annotate(day=TruncDate("date_time"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )


# ── Statutory monthly return ──────────────────────────────────

def monthly_return(year: int, month: int):
    """
    Build the data structure for a NHMIS-style statutory monthly return.
    Returns a dict with all required aggregates.
    """
    from calendar import monthrange

    from admissions.models import Admission
    from encounters.models import Encounter
    from laboratory.models import LabOrder
    from patients.models import Patient

    _, last_day = monthrange(year, month)
    start = date(year, month, 1)
    end = date(year, month, last_day)

    new_patients = Patient.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
    encounters = Encounter.objects.filter(date_time__date__gte=start, date_time__date__lte=end)
    admissions = Admission.objects.filter(admitted_at__date__gte=start, admitted_at__date__lte=end)
    discharges = Admission.objects.filter(discharged_at__date__gte=start, discharged_at__date__lte=end)
    lab_tests = LabOrder.objects.filter(created_at__date__gte=start, created_at__date__lte=end)

    return {
        "period": f"{year}-{month:02d}",
        "new_registrations": new_patients.count(),
        "new_male": new_patients.filter(sex="M").count(),
        "new_female": new_patients.filter(sex="F").count(),
        "total_outpatient_visits": encounters.filter(encounter_type="outpatient").count(),
        "total_inpatient_admissions": admissions.count(),
        "total_discharges": discharges.count(),
        "deaths_inpatient": discharges.filter(
            discharge_type=Admission.DischargeType.DECEASED
        ).count(),
        "lab_tests_ordered": lab_tests.count(),
        "lab_tests_completed": lab_tests.filter(
            status__in=["verified", "released"]
        ).count(),
        "top_diagnoses": list(top_diagnoses(start, end, limit=5)),
        "revenue": revenue_summary(start, end),
    }
