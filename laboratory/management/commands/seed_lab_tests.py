"""
Seed LabTest catalogue with common tests. Safe to re-run.
"""
from django.core.management.base import BaseCommand

LAB_TESTS = [
    # (code, name, sample_type, panel, tat_hours, price, units, ref_range)
    ("FBC",   "Full Blood Count",       "edta_blood",  "haematology", 4,  2500, "varies", "See individual parameters"),
    ("MP-RDT","Malaria Parasite RDT",   "edta_blood",  "parasitology",1,  1500, "",       "Negative"),
    ("MP-THK","Malaria Thick Film",     "edta_blood",  "parasitology",2,  2000, "",       "No parasites seen"),
    ("LFT",   "Liver Function Tests",   "plain_blood", "chemistry",   6,  5000, "varies", "See individual parameters"),
    ("RFT",   "Renal Function Tests",   "plain_blood", "chemistry",   6,  5000, "varies", "See individual parameters"),
    ("URINAL","Urinalysis",             "urine",       "microbiology",2,  1500, "",       "Normal"),
    ("CULT-U","Urine Culture & Sensitivity","urine",   "microbiology",48, 7000, "",       "No significant growth"),
    ("CULT-B","Blood Culture",          "edta_blood",  "microbiology",72, 9000, "",       "No growth"),
    ("HIV",   "HIV 1&2 Rapid Test",     "plain_blood", "serology",    1,  2000, "",       "Non-reactive"),
    ("GLUC-R","Random Blood Glucose",   "plain_blood", "chemistry",   1,  1000, "mmol/L", "3.9–7.8"),
    ("GLUC-F","Fasting Blood Glucose",  "plain_blood", "chemistry",   1,  1200, "mmol/L", "3.9–5.6"),
    ("HBA1C", "HbA1c",                  "edta_blood",  "chemistry",   24, 8000, "%",      "<6.5"),
    ("CHOL",  "Total Cholesterol",      "plain_blood", "chemistry",   6,  3000, "mmol/L", "<5.2"),
    ("WIDAL", "Widal Test",             "plain_blood", "serology",    4,  2500, "",       "Negative"),
    ("PT",    "Prothrombin Time",        "citrate_blood","haematology",4,  3500, "seconds","11–15"),
    ("ESR",   "ESR",                    "edta_blood",  "haematology", 2,  1500, "mm/hr",  "M:<15  F:<20"),
    ("CRP",   "C-Reactive Protein",     "plain_blood", "chemistry",   6,  4000, "mg/L",   "<10"),
    ("PSA",   "PSA (Total)",            "plain_blood", "chemistry",   24, 8000, "ng/mL",  "<4.0"),
    ("PREG",  "Urine Pregnancy Test",   "urine",       "endocrinology",1, 1000, "",       "Negative"),
    ("ECG",   "ECG Interpretation",     "other",       "cardiology",  2,  5000, "",       "Normal sinus rhythm"),
]


class Command(BaseCommand):
    help = "Seed LabTest catalogue with common tests."

    def handle(self, *args, **options):
        from laboratory.models import LabTest

        created = updated = 0
        for code, name, sample, panel, tat, price, units, ref in LAB_TESTS:
            _, c = LabTest.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "sample_type": sample,
                    "panel": panel,
                    "turnaround_hours": tat,
                    "price": price,
                    "units": units,
                    "reference_range_note": ref,
                    "is_active": True,
                },
            )
            if c:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(f"LabTest: {created} created, {updated} updated.")
        )
