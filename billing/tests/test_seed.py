import pytest


@pytest.mark.django_db
def test_seed_catalogue_idempotent():
    from django.core.management import call_command
    from billing.models import ServiceCatalogue

    call_command("seed_catalogue", verbosity=0)
    count_after_first = ServiceCatalogue.objects.count()
    assert count_after_first > 0

    call_command("seed_catalogue", verbosity=0)
    assert ServiceCatalogue.objects.count() == count_after_first


@pytest.mark.django_db
def test_seed_lab_tests_idempotent():
    from django.core.management import call_command
    from laboratory.models import LabTest

    call_command("seed_lab_tests", verbosity=0)
    count = LabTest.objects.count()
    assert count > 0

    call_command("seed_lab_tests", verbosity=0)
    assert LabTest.objects.count() == count


@pytest.mark.django_db
def test_seed_drugs_idempotent():
    from django.core.management import call_command
    from prescriptions.models import Drug

    call_command("seed_drugs", verbosity=0)
    count = Drug.objects.count()
    assert count > 0

    call_command("seed_drugs", verbosity=0)
    assert Drug.objects.count() == count
