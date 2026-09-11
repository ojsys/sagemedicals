from django.db import transaction
from django.utils import timezone


def generate_certificate_number():
    """Generate the next SAGE/BC/YYYY/NNNNN number. Race-safe via SELECT FOR UPDATE."""
    from births.models import BirthCertificateSequence

    year = timezone.localdate().year
    with transaction.atomic():
        seq, _ = BirthCertificateSequence.objects.select_for_update().get_or_create(
            year=year, defaults={"last_value": 0}
        )
        seq.last_value += 1
        seq.save(update_fields=["last_value"])
    return f"SAGE/BC/{year}/{seq.last_value:05d}"
