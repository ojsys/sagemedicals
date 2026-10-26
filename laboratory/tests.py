from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone


@pytest.fixture(autouse=True)
def _reset_audit_user():
    """AuditMiddleware stores the request user on the BaseModel class, which
    otherwise leaks into later tests after that user has been rolled back."""
    yield
    from core.models import BaseModel
    if "_current_user" in vars(BaseModel):
        del BaseModel._current_user


@pytest.fixture
def labtech(db):
    from accounts.models import Role, User
    return User.objects.create_user(
        email="lab@test.ng", password="x", first_name="Tunde", last_name="Bello", role=Role.LAB_TECH,
    )


@pytest.fixture
def patient(db):
    from patients.models import Patient
    return Patient.objects.create(
        hospital_number="SAGE/2026/000101", first_name="Amaka", last_name="Okafor",
        date_of_birth=date(1990, 1, 1), sex="F",
    )


@pytest.fixture
def other_patient(db):
    from patients.models import Patient
    return Patient.objects.create(
        hospital_number="SAGE/2026/000102", first_name="Chinedu", last_name="Obi",
        date_of_birth=date(1985, 6, 1), sex="M",
    )


@pytest.fixture
def fbc(db):
    from laboratory.models import LabTest
    return LabTest.objects.create(code="FBC", name="Full Blood Count", panel="Haematology", price=Decimal("3000"))


@pytest.fixture
def encounter(patient, labtech):
    from encounters.models import Encounter
    return Encounter.objects.create(patient=patient, attending=labtech, date_time=timezone.now())


def _order(patient, test, clinician, hours_ago=0, **kw):
    from laboratory.models import LabOrder
    order = LabOrder.objects.create(patient=patient, test=test, ordering_clinician=clinician, **kw)
    if hours_ago:
        LabOrder.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(hours=hours_ago))
        order.refresh_from_db()
    return order


# ── 48-hour expiry ────────────────────────────────────────────

@pytest.mark.django_db
def test_uncollected_order_expires_after_48h(patient, fbc, labtech):
    from laboratory.models import LabOrder
    from laboratory.services import expire_stale_orders

    stale = _order(patient, fbc, labtech, hours_ago=49)
    fresh = _order(patient, fbc, labtech, hours_ago=47)
    collected = _order(patient, fbc, labtech, hours_ago=72, status=LabOrder.Status.SAMPLE_COLLECTED)

    assert expire_stale_orders() == 1
    stale.refresh_from_db()
    fresh.refresh_from_db()
    collected.refresh_from_db()
    assert stale.status == LabOrder.Status.CANCELLED
    assert stale.was_auto_expired
    assert fresh.status == LabOrder.Status.ORDERED
    assert collected.status == LabOrder.Status.SAMPLE_COLLECTED


@pytest.mark.django_db
def test_expiry_removes_unpaid_billing_line(patient, fbc, labtech, encounter):
    from billing.models import InvoiceItem
    from billing.services import add_invoice_item
    from laboratory.services import expire_stale_orders

    _order(patient, fbc, labtech, hours_ago=50, encounter=encounter)
    add_invoice_item(encounter, "Lab: Full Blood Count", fbc.price)

    expire_stale_orders()
    assert not InvoiceItem.objects.filter(description="Lab: Full Blood Count").exists()


@pytest.mark.django_db
def test_expire_command(patient, fbc, labtech):
    from laboratory.models import LabOrder

    _order(patient, fbc, labtech, hours_ago=60)
    call_command("expire_lab_orders")
    assert LabOrder.objects.get().status == LabOrder.Status.CANCELLED


@pytest.mark.django_db
def test_worklist_load_expires_stale_orders(client, patient, fbc, labtech):
    from laboratory.models import LabOrder

    _order(patient, fbc, labtech, hours_ago=49)
    client.force_login(labtech)
    resp = client.get(reverse("laboratory:worklist"))
    assert resp.status_code == 200
    assert LabOrder.objects.get().status == LabOrder.Status.CANCELLED


# ── Worklist filtering & search ───────────────────────────────

@pytest.mark.django_db
def test_status_tabs_filter_orders(client, patient, fbc, labtech):
    from laboratory.models import LabOrder

    pending = _order(patient, fbc, labtech)
    resulted = _order(patient, fbc, labtech, status=LabOrder.Status.RESULTED)
    client.force_login(labtech)

    resp = client.get(reverse("laboratory:worklist"), {"status": "awaiting_verify"})
    assert list(resp.context["orders"]) == [resulted]

    resp = client.get(reverse("laboratory:worklist"), {"status": "pending"})
    assert list(resp.context["orders"]) == [pending]

    counts = {t["key"]: t["count"] for t in resp.context["tabs"]}
    assert counts["active"] == 2 and counts["pending"] == 1 and counts["awaiting_verify"] == 1


@pytest.mark.django_db
def test_name_search_spans_all_statuses(client, patient, other_patient, fbc, labtech):
    from laboratory.models import LabOrder

    released = _order(patient, fbc, labtech, status=LabOrder.Status.RELEASED)
    _order(other_patient, fbc, labtech)
    client.force_login(labtech)

    resp = client.get(reverse("laboratory:worklist"), {"q": "amaka okafor"})
    assert resp.context["tab"] == "all"
    assert list(resp.context["orders"]) == [released]


@pytest.mark.django_db
def test_htmx_search_returns_partial(client, patient, fbc, labtech):
    _order(patient, fbc, labtech)
    client.force_login(labtech)
    resp = client.get(reverse("laboratory:worklist"), {"q": "SAGE/2026/000101"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    assert [t.name for t in resp.templates][0] == "laboratory/partials/worklist_results.html"
    assert b"Amaka Okafor" in resp.content


@pytest.mark.django_db
def test_worklist_is_paginated(client, patient, fbc, labtech):
    from laboratory.views import WORKLIST_PAGE_SIZE

    for _ in range(WORKLIST_PAGE_SIZE + 3):
        _order(patient, fbc, labtech)
    client.force_login(labtech)
    resp = client.get(reverse("laboratory:worklist"), {"page": 2})
    assert len(resp.context["orders"]) == 3


@pytest.mark.django_db
def test_stat_orders_lead_the_queue(client, patient, fbc, labtech):
    from laboratory.models import LabOrder

    routine = _order(patient, fbc, labtech, hours_ago=5)
    stat = _order(patient, fbc, labtech, priority=LabOrder.Priority.STAT)
    client.force_login(labtech)
    resp = client.get(reverse("laboratory:worklist"))
    assert list(resp.context["orders"]) == [stat, routine]


# ── Bulk actions ──────────────────────────────────────────────

@pytest.mark.django_db
def test_bulk_collect_and_cancel(client, patient, fbc, labtech):
    from laboratory.models import LabOrder

    a = _order(patient, fbc, labtech)
    b = _order(patient, fbc, labtech)
    released = _order(patient, fbc, labtech, status=LabOrder.Status.RELEASED)
    client.force_login(labtech)
    url = reverse("laboratory:bulk_action")
    back = reverse("laboratory:worklist") + "?status=pending"

    resp = client.post(url, {"action": "collect", "orders": [a.pk], "next": back})
    assert resp.status_code == 302 and resp.url == back
    a.refresh_from_db()
    assert a.status == LabOrder.Status.SAMPLE_COLLECTED and a.collected_by == labtech

    client.post(url, {"action": "cancel", "orders": [b.pk, released.pk], "reason": "Patient left"})
    b.refresh_from_db()
    released.refresh_from_db()
    assert b.status == LabOrder.Status.CANCELLED and b.cancel_reason.startswith("Patient left")
    assert released.status == LabOrder.Status.RELEASED


@pytest.mark.django_db
def test_bulk_action_rejects_offsite_next(client, patient, fbc, labtech):
    a = _order(patient, fbc, labtech)
    client.force_login(labtech)
    resp = client.post(reverse("laboratory:bulk_action"),
                       {"action": "collect", "orders": [a.pk], "next": "https://evil.example/"})
    assert resp.url == reverse("laboratory:worklist")
