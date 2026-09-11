from datetime import date, time, timedelta
from decimal import Decimal

import pytest
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
def nurse(db):
    from accounts.models import Role, User
    return User.objects.create_user(
        email="nurse@test.ng", password="x",
        first_name="Ngozi", last_name="Eze", role=Role.NURSE,
    )


@pytest.fixture
def portal_user(db):
    from accounts.models import Role, User
    return User.objects.create_user(email="patient@test.ng", password="x", role=Role.PATIENT)


@pytest.fixture
def mother(db):
    from patients.models import Patient
    return Patient.objects.create(
        hospital_number="SAGE/2026/000010",
        first_name="Amaka", last_name="Okafor",
        date_of_birth=date(1994, 5, 2), sex="F",
    )


def _record(mother, **overrides):
    from births.models import BirthRecord
    data = {
        "mother": mother,
        "child_first_name": "Chidera", "child_surname": "Okafor", "sex": "F",
        "date_of_birth": date(2026, 9, 5), "time_of_birth": time(14, 32),
        "weight_kg": Decimal("3.20"),
    }
    data.update(overrides)
    return BirthRecord.objects.create(**data)


# ── Model ─────────────────────────────────────────────────────

@pytest.mark.django_db
def test_certificate_numbers_are_sequential(mother):
    year = timezone.localdate().year
    assert _record(mother).certificate_number == f"SAGE/BC/{year}/00001"
    assert _record(mother).certificate_number == f"SAGE/BC/{year}/00002"


@pytest.mark.django_db
def test_birth_type_display(mother):
    assert _record(mother).birth_type_display == "Singleton"
    assert _record(mother, babies_in_delivery=2, birth_order=2).birth_type_display == "Twin 2 of 2"


# ── Certificate PDF ───────────────────────────────────────────

@pytest.mark.django_db
def test_certificate_pdf_view_returns_pdf(client, nurse, mother):
    record = _record(
        mother, attended_by=nurse, delivery_mode="cs", father_name="Emeka Okafor",
        length_cm=Decimal("50.5"), gestational_age_weeks=39,
    )
    client.force_login(nurse)
    resp = client.get(reverse("births:certificate", args=[record.pk]))
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/pdf"
    assert resp["Content-Disposition"].startswith("inline;")
    assert resp.content[:4] == b"%PDF"

    resp = client.get(reverse("births:certificate", args=[record.pk]) + "?download=1")
    assert resp["Content-Disposition"].startswith("attachment;")


@pytest.mark.django_db
def test_certificate_survives_very_long_names(mother):
    from births.certificate import build_birth_certificate_pdf
    record = _record(
        mother, child_first_name="A" * 100, child_middle_name="B" * 100,
        child_surname="C" * 100, father_name="D" * 200,
    )
    assert build_birth_certificate_pdf(record).read()[:4] == b"%PDF"


# ── Access ────────────────────────────────────────────────────

@pytest.mark.django_db
def test_patient_role_cannot_access_register(client, portal_user, mother):
    record = _record(mother)
    client.force_login(portal_user)
    assert client.get(reverse("births:list")).status_code == 403
    assert client.get(reverse("births:certificate", args=[record.pk])).status_code == 403


@pytest.mark.django_db
def test_staff_pages_render(client, nurse, mother):
    from antenatal.models import ANCRecord
    anc = ANCRecord.objects.create(
        patient=mother, edd=date(2026, 9, 12), outcome="delivered",
        outcome_date=date(2026, 9, 5), is_active=False,
    )
    record = _record(mother, anc_record=anc, attended_by=nurse, notes="Cried at birth.")
    client.force_login(nurse)

    for url in [
        reverse("births:list"),
        reverse("births:list") + "?q=Chidera",
        reverse("births:create"),
        reverse("births:detail", args=[record.pk]),
        reverse("births:edit", args=[record.pk]),
    ]:
        assert client.get(url).status_code == 200, url

    anc_page = client.get(reverse("antenatal:detail", args=[anc.pk]))
    assert anc_page.status_code == 200
    assert f"?anc={anc.pk}" in anc_page.content.decode()
    assert record.certificate_number in anc_page.content.decode()


# ── Registering a birth ───────────────────────────────────────

@pytest.mark.django_db
def test_register_birth_creates_record(client, nurse, mother):
    from births.models import BirthRecord
    client.force_login(nurse)
    resp = client.post(reverse("births:create"), {
        "mother": mother.pk,
        "child_first_name": "Obinna", "child_surname": "Okafor", "sex": "M",
        "date_of_birth": (timezone.localdate() - timedelta(days=1)).isoformat(),
        "time_of_birth": "08:15", "weight_kg": "3.4",
        "birth_order": 1, "babies_in_delivery": 1,
        "attended_by": nurse.pk,
    })
    record = BirthRecord.objects.get()
    assert resp.status_code == 302
    assert resp["Location"] == reverse("births:detail", args=[record.pk])
    assert record.mother == mother
    assert record.created_by == nurse


@pytest.mark.django_db
def test_form_rejects_birth_order_above_babies_delivered():
    from births.forms import BirthRecordForm
    form = BirthRecordForm(data={
        "child_first_name": "Kene", "child_surname": "Obi", "sex": "F",
        "date_of_birth": timezone.localdate().isoformat(), "time_of_birth": "10:00",
        "weight_kg": "2.9", "birth_order": 3, "babies_in_delivery": 2,
    })
    assert not form.is_valid()
    assert "birth_order" in form.errors


@pytest.mark.django_db
def test_form_rejects_future_birth_date():
    from births.forms import BirthRecordForm
    form = BirthRecordForm(data={
        "child_first_name": "Kene", "child_surname": "Obi", "sex": "F",
        "date_of_birth": (timezone.localdate() + timedelta(days=1)).isoformat(),
        "time_of_birth": "10:00", "weight_kg": "2.9",
        "birth_order": 1, "babies_in_delivery": 1,
    })
    assert not form.is_valid()
    assert "date_of_birth" in form.errors


@pytest.mark.django_db
def test_create_prefills_from_delivered_anc_record(client, nurse, mother):
    from antenatal.models import ANCRecord
    anc = ANCRecord.objects.create(
        patient=mother, lmp=date(2025, 12, 6), edd=date(2026, 9, 12),
        outcome="delivered", outcome_date=date(2026, 9, 5),
        delivery_mode="cs", babies_count=2, is_active=False,
    )
    _record(mother, anc_record=anc, babies_in_delivery=2)  # first twin already registered

    client.force_login(nurse)
    resp = client.get(reverse("births:create") + f"?anc={anc.pk}")
    initial = resp.context["form"].initial
    assert resp.context["mother"] == mother
    assert initial["date_of_birth"] == date(2026, 9, 5)
    assert initial["gestational_age_weeks"] == 39
    assert initial["delivery_mode"] == "cs"
    assert initial["babies_in_delivery"] == 2
    assert initial["birth_order"] == 2
