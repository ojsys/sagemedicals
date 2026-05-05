"""
Seed the ServiceCatalogue with common service codes.
Safe to run multiple times — uses update_or_create on code.
"""
from django.core.management.base import BaseCommand

SERVICES = [
    # (code, name, category, self_pay, nhia, hmo)
    ("CONS-GP",    "General Practitioner Consultation",  "consultation", 3000,  1500, 2500),
    ("CONS-SPEC",  "Specialist Consultation",            "consultation", 8000,  3000, 6000),
    ("CONS-EMERG", "Emergency Consultation",             "consultation", 5000,  2000, 4000),
    ("LAB-FBC",    "Full Blood Count",                   "lab",          2500,  1000, 2000),
    ("LAB-MP",     "Malaria Parasite (RDT)",             "lab",          1500,   500, 1200),
    ("LAB-LFT",    "Liver Function Tests",               "lab",          5000,  2000, 4000),
    ("LAB-RFT",    "Renal Function Tests",               "lab",          5000,  2000, 4000),
    ("LAB-URINE",  "Urinalysis",                         "lab",          1500,   500, 1200),
    ("LAB-CULT",   "Culture & Sensitivity",              "lab",          7000,  3000, 5500),
    ("LAB-HIV",    "HIV Rapid Test",                     "lab",          2000,   800, 1600),
    ("LAB-GLUCOS", "Random Blood Glucose",               "lab",          1000,   400,  800),
    ("LAB-HBA1C",  "HbA1c",                              "lab",          8000,  3000, 6000),
    ("IMG-XRAY",   "X-Ray (any site)",                   "imaging",     10000,  4000, 8000),
    ("IMG-USS",    "Ultrasound Scan",                    "imaging",     15000,  6000,12000),
    ("IMG-ECG",    "ECG",                                "imaging",      5000,  2000, 4000),
    ("PROC-IV",    "IV Line Insertion",                  "procedure",    2000,   800, 1500),
    ("PROC-DRESS", "Wound Dressing",                     "procedure",    2500,  1000, 2000),
    ("PROC-SUTURE","Suturing",                           "procedure",    5000,  2000, 4000),
    ("ADM-BED",    "Bed/Day (General Ward)",             "admission",   10000,  4000, 8000),
    ("ADM-BED-SB", "Bed/Day (Side Room)",                "admission",   20000,  8000,15000),
]


class Command(BaseCommand):
    help = "Seed ServiceCatalogue with standard services."

    def handle(self, *args, **options):
        from billing.models import ServiceCatalogue

        created_count = updated_count = 0
        for code, name, category, self_pay, nhia, hmo in SERVICES:
            _, created = ServiceCatalogue.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "category": category,
                    "self_pay_price": self_pay,
                    "nhia_price": nhia,
                    "hmo_price": hmo,
                    "is_active": True,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"ServiceCatalogue: {created_count} created, {updated_count} updated."
            )
        )
