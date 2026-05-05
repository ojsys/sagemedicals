"""
Seed Drug formulary with common essential medicines. Safe to re-run.
"""
from django.core.management.base import BaseCommand

DRUGS = [
    # (generic_name, brand_name, strength, dosage_form, route, category, atc)
    ("Amoxicillin",         "",                "500mg",   "capsule",  "oral",  "pom",  "J01CA04"),
    ("Amoxicillin/Clavulanate","Augmentin",   "625mg",   "tablet",   "oral",  "pom",  "J01CR02"),
    ("Azithromycin",        "Zithromax",       "500mg",   "tablet",   "oral",  "pom",  "J01FA10"),
    ("Ciprofloxacin",       "",                "500mg",   "tablet",   "oral",  "pom",  "J01MA02"),
    ("Metronidazole",       "Flagyl",          "400mg",   "tablet",   "oral",  "pom",  "P01AB01"),
    ("Metronidazole IV",    "Flagyl IV",       "500mg/100ml","infusion","iv", "pom",  "P01AB01"),
    ("Artemether/Lumefantrine","Coartem",      "20/120mg","tablet",   "oral",  "pom",  "P01BF01"),
    ("Artesunate",          "",                "100mg",   "injection","iv",   "pom",  "P01BE03"),
    ("Dihydroartemisinin/Piperaquine","Eurartesim","40/320mg","tablet","oral","pom","P01BF51"),
    ("Paracetamol",         "Panadol",         "500mg",   "tablet",   "oral",  "otc",  "N02BE01"),
    ("Paracetamol IV",      "Perfalgan",       "1g/100ml","infusion","iv",   "pom",  "N02BE01"),
    ("Ibuprofen",           "",                "400mg",   "tablet",   "oral",  "otc",  "M01AE01"),
    ("Diclofenac",          "Voltaren",        "75mg",    "injection","im",   "pom",  "M01AB05"),
    ("Tramadol",            "Tramal",          "50mg",    "capsule",  "oral",  "pom",  "N02AX02"),
    ("Morphine",            "",                "10mg/ml", "injection","iv",   "pom",  "N02AA01"),
    ("Amlodipine",          "Norvasc",         "5mg",     "tablet",   "oral",  "pom",  "C08CA01"),
    ("Lisinopril",          "Zestril",         "10mg",    "tablet",   "oral",  "pom",  "C09AA03"),
    ("Atenolol",            "",                "50mg",    "tablet",   "oral",  "pom",  "C07AB03"),
    ("Metformin",           "Glucophage",      "500mg",   "tablet",   "oral",  "pom",  "A10BA02"),
    ("Glibenclamide",       "Daonil",          "5mg",     "tablet",   "oral",  "pom",  "A10BB01"),
    ("Insulin (Regular)",   "Actrapid",        "100IU/ml","injection","sc",   "pom",  "A10AB01"),
    ("Insulin (NPH)",       "Insulatard",      "100IU/ml","injection","sc",   "pom",  "A10AC01"),
    ("Salbutamol",          "Ventolin",        "100mcg",  "inhaler",  "inhalation","pom","R03AC02"),
    ("Prednisolone",        "",                "5mg",     "tablet",   "oral",  "pom",  "H02AB06"),
    ("Hydrocortisone",      "",                "100mg",   "injection","iv",   "pom",  "H02AB09"),
    ("Furosemide",          "Lasix",           "40mg",    "tablet",   "oral",  "pom",  "C03CA01"),
    ("Furosemide IV",       "Lasix IV",        "40mg/4ml","injection","iv",   "pom",  "C03CA01"),
    ("Spironolactone",      "Aldactone",       "25mg",    "tablet",   "oral",  "pom",  "C03DA01"),
    ("Omeprazole",          "Losec",           "20mg",    "capsule",  "oral",  "pom",  "A02BC01"),
    ("Pantoprazole IV",     "",                "40mg",    "injection","iv",   "pom",  "A02BC02"),
    ("Oral Rehydration Salts","ORS",           "one sachet","sachet", "oral",  "otc",  "A07CA"),
    ("Zinc Sulfate",        "",                "20mg",    "tablet",   "oral",  "otc",  "A12CB01"),
    ("Folic Acid",          "",                "5mg",     "tablet",   "oral",  "otc",  "B03BB01"),
    ("Ferrous Sulfate",     "",                "200mg",   "tablet",   "oral",  "otc",  "B03AA07"),
    ("Calcium Gluconate",   "",                "1g/10ml", "injection","iv",   "pom",  "A12AA03"),
    ("Diazepam",            "Valium",          "10mg/2ml","injection","iv",   "pom",  "N05BA01"),
    ("Phenytoin",           "Epanutin",        "100mg",   "tablet",   "oral",  "pom",  "N03AB02"),
    ("Haloperidol",         "Serenace",        "5mg",     "tablet",   "oral",  "pom",  "N05AD01"),
    ("Gentamicin",          "",                "80mg/2ml","injection","im",   "pom",  "J01GB03"),
    ("Ceftriaxone",         "Rocephin",        "1g",      "injection","iv",   "pom",  "J01DD04"),
]


class Command(BaseCommand):
    help = "Seed Drug formulary with common essential medicines."

    def handle(self, *args, **options):
        from prescriptions.models import Drug

        created = updated = 0
        for generic, brand, strength, form, route, cat, atc in DRUGS:
            key = f"{generic}|{strength}|{form}"
            _, c = Drug.objects.update_or_create(
                generic_name=generic,
                strength=strength,
                dosage_form=form,
                defaults={
                    "brand_name": brand,
                    "default_route": route,
                    "category": cat,
                    "atc_code": atc,
                    "is_formulary": True,
                    "is_active": True,
                },
            )
            if c:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(f"Drug formulary: {created} created, {updated} updated.")
        )
