"""
Seed realistic development data for SAGE EMR.

Creates staff, patients, clinics, appointments, encounters, vitals, diagnoses,
prescriptions, lab orders/results, pharmacy stock, ward beds, admissions,
billing invoices, surgery bookings, and notifications.

Safe to run multiple times — uses get_or_create / update_or_create throughout.
Usage:
    python manage.py seed_dev_data
    python manage.py seed_dev_data --reset   # wipe clinical data first, then re-seed
"""
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.utils import timezone


# ── helpers ──────────────────────────────────────────────────────────────────

def dt(days_offset=0, hour=8, minute=0):
    """Return a UTC-aware datetime relative to today at Africa/Lagos (UTC+1)."""
    d = date.today() + timedelta(days=days_offset)
    naive = timezone.datetime(d.year, d.month, d.day, hour, minute, 0)
    return timezone.make_aware(naive)


def today_plus(days=0):
    return date.today() + timedelta(days=days)


# ── master data ───────────────────────────────────────────────────────────────

STAFF = [
    # (email, first, last, role, department, phone)
    ("chukwuemeka.okafor@sagemed.ng",  "Chukwuemeka", "Okafor",    "doctor",         "Internal Medicine", "+2348031234561"),
    ("amina.bello@sagemed.ng",         "Amina",        "Bello",     "doctor",         "Cardiology",        "+2348031234562"),
    ("ngozi.adeyemi@sagemed.ng",       "Ngozi",        "Adeyemi",   "resident",       "General Medicine",  "+2348031234563"),
    ("fatima.usman@sagemed.ng",        "Fatima",       "Usman",     "nurse",          "Outpatient",        "+2348031234564"),
    ("samuel.obi@sagemed.ng",          "Samuel",       "Obi",       "nurse",          "Ward A",            "+2348031234565"),
    ("kelechi.nwachukwu@sagemed.ng",   "Kelechi",      "Nwachukwu", "pharmacist",     "Pharmacy",          "+2348031234566"),
    ("ibrahim.musa@sagemed.ng",        "Ibrahim",      "Musa",      "lab_tech",       "Laboratory",        "+2348031234567"),
    ("tunde.adewale@sagemed.ng",       "Tunde",        "Adewale",   "billing_officer","Billing",           "+2348031234568"),
    ("grace.eze@sagemed.ng",           "Grace",        "Eze",       "receptionist",   "Reception",         "+2348031234569"),
    ("olabisi.fashola@sagemed.ng",     "Olabisi",      "Fashola",   "hospital_admin", "Administration",    "+2348031234570"),
]

PATIENTS_DATA = [
    # (hosp_num, first, mid, last, dob_str, sex, blood, marital, phone, email,
    #  state, religion, payer, hmo_name, hmo_number, occupation)
    ("SAGE/2024/000001", "Emeka",    "Chukwu",   "Okonkwo",   "1979-03-14", "M", "O+",  "married",
     "+2348051234501", "emeka.okonkwo@gmail.com",   "Lagos",   "Christianity", "self_pay",   "",          "",          "Civil Servant"),
    ("SAGE/2024/000002", "Chidinma", "Adaeze",   "Okafor",    "1992-07-22", "F", "A+",  "married",
     "+2348051234502", "chidinma.okafor@yahoo.com", "Anambra", "Christianity", "private_hmo","Hygeia HMO","HYG-2024-88723","Teacher"),
    ("SAGE/2023/000145", "Musa",     "",         "Abdullahi", "1956-11-05", "M", "B+",  "married",
     "+2348051234503", "",                          "Kano",    "Islam",        "nhia",       "",          "",          "Retired"),
    ("SAGE/2025/000018", "Ngozi",    "Chinyere", "Eze",       "1997-04-30", "F", "O-",  "single",
     "+2348051234504", "ngozi.eze@gmail.com",       "Enugu",   "Christianity", "self_pay",   "",          "",          "Student"),
    ("SAGE/2024/000089", "Taiwo",    "Babatunde","Adeyemi",   "1972-09-18", "M", "AB+", "married",
     "+2348051234505", "t.adeyemi@zenithbank.com",  "Ogun",    "Christianity", "corporate",  "",          "",          "Banker"),
    ("SAGE/2024/000210", "Aisha",    "",         "Mohammed",  "1983-01-27", "F", "A-",  "married",
     "+2348051234506", "aisha.m@gmail.com",         "FCT Abuja","Islam",       "private_hmo","AXA Mansard","AXA-NG-55891","Business Owner"),
    ("SAGE/2022/000033", "Chukwudi", "",         "Nwosu",     "2009-06-11", "M", "SS",  "single",
     "+2348051234507", "",                          "Imo",     "Christianity", "self_pay",   "",          "",          "Student"),
    ("SAGE/2021/000007", "Bola",     "Adunola",  "Afolabi",   "1952-12-02", "F", "B-",  "widowed",
     "+2348051234508", "",                          "Oyo",     "Christianity", "self_pay",   "",          "",          "Retired"),
    ("SAGE/2025/000102", "Segun",    "",         "Williams",  "1986-08-19", "M", "O+",  "single",
     "+2348051234509", "segun.w@outlook.com",       "Rivers",  "Christianity", "self_pay",   "",          "",          "Engineer"),
    ("SAGE/2026/000001", "Halima",   "Maryam",   "Yusuf",     "2000-02-14", "F", "A+",  "single",
     "+2348051234510", "halima.yusuf@gmail.com",    "Kaduna",  "Islam",        "nhia",       "",          "",          "Nurse"),
    # ── additional patients ───────────────────────────────────────────────────
    ("SAGE/2024/000312", "Adaeze",   "Ugochi",   "Obiora",    "1988-05-16", "F", "O+",  "married",
     "+2348051234511", "adaeze.obiora@gmail.com",   "Anambra", "Christianity", "private_hmo","Leadway HMO","LW-2024-33201","Accountant"),
    ("SAGE/2024/000313", "Yusuf",    "",         "Garba",     "1964-09-03", "M", "A+",  "married",
     "+2348051234512", "",                          "Katsina", "Islam",        "nhia",       "",          "",          "Farmer"),
    ("SAGE/2025/000220", "Temitope", "Blessing", "Ogunleye",  "2003-11-28", "F", "B+",  "single",
     "+2348051234513", "temitope.o@gmail.com",      "Osun",    "Christianity", "self_pay",   "",          "",          "Student"),
    ("SAGE/2023/000402", "Emmanuel", "",         "Ikechukwu", "1969-02-14", "M", "O-",  "married",
     "+2348051234514", "e.ikechukwu@yahoo.com",     "Enugu",   "Christianity", "corporate",  "",          "",          "Trader"),
    ("SAGE/2026/000048", "Fatimah",  "Zainab",   "Ibrahim",   "1995-07-07", "F", "AB+", "married",
     "+2348051234515", "fatimah.ibrahim@gmail.com", "Sokoto",  "Islam",        "self_pay",   "",          "",          "Pharmacist"),
    ("SAGE/2025/000315", "Oluseun",  "",         "Adesanya",  "1978-04-22", "M", "B-",  "married",
     "+2348051234516", "oluseun.a@gmail.com",       "Lagos",   "Christianity", "private_hmo","Total HMO","TOT-2025-77441","Journalist"),
    ("SAGE/2024/000555", "Khadijat", "",         "Salami",    "1949-12-30", "F", "A+",  "widowed",
     "+2348051234517", "",                          "Kwara",   "Islam",        "nhia",       "",          "",          "Retired"),
    ("SAGE/2026/000099", "Obinna",   "Chike",    "Nwofor",    "1991-03-05", "M", "O+",  "single",
     "+2348051234518", "obinna.n@gmail.com",        "Imo",     "Christianity", "self_pay",   "",          "",          "Engineer"),
    ("SAGE/2023/000610", "Risikat",  "Folake",   "Adeleke",   "1972-06-18", "F", "B+",  "married",
     "+2348051234519", "risikat.a@outlook.com",     "Oyo",     "Christianity", "private_hmo","Hygeia HMO","HYG-2023-44109","Nurse"),
    ("SAGE/2025/000440", "Dauda",    "",         "Maikudi",   "1980-10-11", "M", "A-",  "married",
     "+2348051234520", "",                          "Bauchi",  "Islam",        "nhia",       "",          "",          "Civil Servant"),
]

ALLERGIES = {
    "SAGE/2024/000001": [
        ("Penicillin",        "drug",  "severe",          "Urticaria, angioedema"),
        ("Aspirin",           "drug",  "moderate",        "GI upset, bronchospasm"),
    ],
    "SAGE/2023/000145": [
        ("Sulphonamides",     "drug",  "severe",          "Stevens-Johnson syndrome history"),
    ],
    "SAGE/2024/000210": [
        ("Peanuts",           "food",  "life_threatening","Anaphylaxis"),
        ("Latex",             "latex", "moderate",        "Contact dermatitis"),
    ],
    "SAGE/2022/000033": [
        ("NSAIDs",            "drug",  "severe",          "Aplastic crisis precipitant"),
    ],
}

CHRONIC_CONDITIONS = {
    "SAGE/2024/000001": [
        ("I10",   "Essential Hypertension",              "active",  "2018-06-01"),
        ("E11.9", "Type 2 Diabetes Mellitus",            "active",  "2019-03-15"),
    ],
    "SAGE/2023/000145": [
        ("N18.3", "Chronic Kidney Disease Stage 3",      "active",  "2020-01-10"),
        ("I10",   "Essential Hypertension",              "active",  "2015-04-20"),
        ("E11.9", "Type 2 Diabetes Mellitus",            "active",  "2017-09-08"),
    ],
    "SAGE/2024/000089": [
        ("E78.5", "Mixed Hyperlipidaemia",               "active",  "2021-02-14"),
        ("I20.9", "Angina Pectoris",                     "active",  "2023-05-30"),
    ],
    "SAGE/2021/000007": [
        ("M05.9", "Rheumatoid Arthritis",                "active",  "2010-07-12"),
        ("I10",   "Essential Hypertension",              "active",  "2012-11-03"),
        ("M81.0", "Osteoporosis",                        "active",  "2016-02-28"),
    ],
    "SAGE/2022/000033": [
        ("D57.1", "Sickle Cell Anaemia (HbSS)",          "active",  "2009-06-15"),
    ],
}

NOK_DATA = {
    "SAGE/2024/000001": ("Adaeze Okonkwo",    "spouse",   "+2348061234501"),
    "SAGE/2024/000002": ("Emmanuel Okafor",   "spouse",   "+2348061234502"),
    "SAGE/2023/000145": ("Fatima Abdullahi",  "spouse",   "+2348061234503"),
    "SAGE/2025/000018": ("Chukwuma Eze",      "parent",   "+2348061234504"),
    "SAGE/2024/000089": ("Folake Adeyemi",    "spouse",   "+2348061234505"),
    "SAGE/2022/000033": ("Obiageli Nwosu",    "parent",   "+2348061234506"),
    "SAGE/2021/000007": ("Tunde Afolabi",     "child",    "+2348061234507"),
}


class Command(BaseCommand):
    help = "Seed development data for UI template development."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all clinical data before re-seeding.",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self._reset()

        self.stdout.write("Seeding development data…")

        staff      = self._seed_staff()
        patients   = self._seed_patients()
        clinics    = self._seed_clinics(staff)
        appts      = self._seed_appointments(patients, clinics, staff)
        queue      = self._seed_queue(patients, clinics, appts)
        encounters = self._seed_encounters(patients, staff, queue)
        self._seed_lab(patients, encounters, staff)
        self._seed_pharmacy(staff)
        beds       = self._seed_wards(staff)
        admissions = self._seed_admissions(patients, beds, staff, encounters)
        self._seed_billing(patients, encounters, staff)
        self._seed_surgery(patients, staff, admissions)
        self._seed_notifications(patients)

        self.stdout.write(self.style.SUCCESS("✔  Seed complete."))

    # ─── reset ────────────────────────────────────────────────────────────────

    def _reset(self):
        self.stdout.write(self.style.WARNING("Resetting clinical data…"))
        from surgery.models import SurgeryBooking, Theatre
        from admissions.models import Admission, BedTransfer, WardRound, MedicationAdministration
        from billing.models import Invoice, Payment
        from laboratory.models import LabOrder
        from pharmacy.models import Dispense, DrugBatch, StockLevel, StockAdjustment
        from prescriptions.models import Prescription
        from encounters.models import Encounter
        from scheduling.models import Appointment, QueueEntry, Clinic, ClinicSchedule
        from patients.models import Patient, Allergy, ChronicCondition, NextOfKin

        for Model in [
            MedicationAdministration, WardRound, BedTransfer, Admission,
            SurgeryBooking, Theatre,
            Payment, Invoice,
            LabOrder,
            Dispense, DrugBatch, StockLevel, StockAdjustment,
            Prescription,
            Encounter,
            QueueEntry, Appointment, ClinicSchedule, Clinic,
            Allergy, ChronicCondition, NextOfKin, Patient,
        ]:
            Model.objects.all().delete()

    # ─── staff ────────────────────────────────────────────────────────────────

    def _seed_staff(self):
        from accounts.models import User
        staff = {}
        pw = make_password("SageDemo@2026")
        for email, first, last, role, dept, phone in STAFF:
            u, _ = User.objects.update_or_create(
                email=email,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "role": role,
                    "department": dept,
                    "phone": phone,
                    "is_active": True,
                    "is_staff": role in ("hospital_admin", "super_admin"),
                    "password": pw,
                },
            )
            staff[role] = staff.get(role) or u
            staff[email] = u
        self.stdout.write(f"  Staff: {len(STAFF)} users")
        return staff

    # ─── patients ─────────────────────────────────────────────────────────────

    def _seed_patients(self):
        from patients.models import Patient, Allergy, ChronicCondition, NextOfKin

        patients = {}
        for row in PATIENTS_DATA:
            (hn, first, mid, last, dob_str, sex, blood, marital,
             phone, email, state, religion, payer, hmo_name, hmo_number, occ) = row

            p, _ = Patient.objects.update_or_create(
                hospital_number=hn,
                defaults={
                    "first_name": first,
                    "middle_name": mid,
                    "last_name": last,
                    "date_of_birth": date.fromisoformat(dob_str),
                    "sex": sex[:1],
                    "blood_group": blood,
                    "marital_status": marital,
                    "phone": phone,
                    "email": email,
                    "address_state": state,
                    "religion": religion,
                    "payer_type": payer,
                    "hmo_name": hmo_name,
                    "hmo_number": hmo_number,
                    "occupation": occ,
                    "preferred_language": "English" if religion != "Islam" else "Hausa",
                    "is_active": True,
                },
            )
            patients[hn] = p

        # Allergies
        for hn, allergy_list in ALLERGIES.items():
            p = patients.get(hn)
            if not p:
                continue
            for allergen, atype, severity, reaction in allergy_list:
                Allergy.objects.get_or_create(
                    patient=p, allergen=allergen,
                    defaults={
                        "allergy_type": atype,
                        "severity": severity,
                        "reaction": reaction,
                        "is_active": True,
                        "date_recorded": today_plus(-90),
                    },
                )

        # Chronic conditions
        for hn, cond_list in CHRONIC_CONDITIONS.items():
            p = patients.get(hn)
            if not p:
                continue
            for icd, desc, status, onset_str in cond_list:
                ChronicCondition.objects.get_or_create(
                    patient=p, icd10_code=icd,
                    defaults={
                        "description": desc,
                        "status": status,
                        "onset_date": date.fromisoformat(onset_str),
                    },
                )

        # Next-of-kin
        for hn, (full_name, rel, phone) in NOK_DATA.items():
            p = patients.get(hn)
            if not p:
                continue
            NextOfKin.objects.update_or_create(
                patient=p,
                defaults={"full_name": full_name, "relationship": rel, "phone": phone},
            )

        # Stamp 2026-registered patients with today's date so the dashboard
        # "Today's Patients" count reflects a realistic new-registration figure.
        today_hns = [hn for hn in patients if hn.startswith("SAGE/2026/")]
        from patients.models import Patient as _P
        _P.objects.filter(hospital_number__in=today_hns).update(
            created_at=timezone.now()
        )

        self.stdout.write(f"  Patients: {len(PATIENTS_DATA)} records")
        return patients

    # ─── clinics & schedules ──────────────────────────────────────────────────

    def _seed_clinics(self, staff):
        from scheduling.models import Clinic, ClinicSchedule

        clinic_defs = [
            ("General Outpatient Clinic",  "General Medicine",    "OPD Block A"),
            ("Cardiology Clinic",          "Cardiology",          "Specialist Block"),
            ("Ante-natal Clinic",          "Obstetrics & Gynae",  "OPD Block B"),
            ("Emergency Department",       "Accident & Emergency","A&E"),
        ]
        clinics = {}
        for name, dept, loc in clinic_defs:
            c, _ = Clinic.objects.update_or_create(
                name=name,
                defaults={"department": dept, "location": loc, "is_active": True},
            )
            clinics[name] = c

        doctor     = staff.get("doctor")
        cardio_doc = staff.get("amina.bello@sagemed.ng")
        gp_doc     = staff.get("chukwuemeka.okafor@sagemed.ng")

        sched_defs = [
            (clinics["General Outpatient Clinic"], gp_doc,     [0,1,2,3,4], time(8,0),  time(16,0), 20, 3),
            (clinics["Cardiology Clinic"],         cardio_doc,  [1,3],       time(9,0),  time(13,0), 30, 1),
            (clinics["Ante-natal Clinic"],         gp_doc,     [2,4],       time(8,0),  time(12,0), 20, 2),
            (clinics["Emergency Department"],      gp_doc,     [0,1,2,3,4,5,6], time(0,0), time(23,59), 10, 5),
        ]
        for clinic, consultant, wdays, start, end, slot_min, per_slot in sched_defs:
            if consultant:
                ClinicSchedule.objects.update_or_create(
                    clinic=clinic, consultant=consultant,
                    defaults={
                        "working_days": wdays,
                        "start_time": start,
                        "end_time": end,
                        "slot_duration_minutes": slot_min,
                        "max_per_slot": per_slot,
                        "is_active": True,
                    },
                )
        self.stdout.write(f"  Clinics: {len(clinics)} defined")
        return clinics

    # ─── appointments ─────────────────────────────────────────────────────────

    def _seed_appointments(self, patients, clinics, staff):
        from scheduling.models import Appointment, ClinicSchedule

        gp_clinic  = clinics["General Outpatient Clinic"]
        ae_clinic  = clinics["Emergency Department"]
        gp_doc     = staff.get("chukwuemeka.okafor@sagemed.ng")
        cardio_doc = staff.get("amina.bello@sagemed.ng")
        cardio_cl  = clinics["Cardiology Clinic"]

        try:
            gp_sched   = ClinicSchedule.objects.get(clinic=gp_clinic, consultant=gp_doc)
            ae_sched   = ClinicSchedule.objects.get(clinic=ae_clinic, consultant=gp_doc)
            card_sched = ClinicSchedule.objects.get(clinic=cardio_cl, consultant=cardio_doc)
        except ClinicSchedule.DoesNotExist:
            self.stdout.write(self.style.WARNING("  Schedules not found — skipping appointments."))
            return {}

        anc_clinic = clinics["Ante-natal Clinic"]
        try:
            anc_sched = ClinicSchedule.objects.get(clinic=anc_clinic, consultant=gp_doc)
        except ClinicSchedule.DoesNotExist:
            anc_sched = gp_sched

        appt_defs = [
            # ── today ──────────────────────────────────────────────────────────
            (patients["SAGE/2024/000210"], ae_sched,   gp_doc,     ae_clinic,   today_plus(0),  time(7,30),  "new",       "completed",   "emergency","Severe allergic reaction — anaphylaxis"),
            (patients["SAGE/2024/000001"], gp_sched,   gp_doc,     gp_clinic,   today_plus(0),  time(8,0),   "followup",  "checked_in",  "normal",   "Routine HTN/DM review — monthly"),
            (patients["SAGE/2025/000018"], gp_sched,   gp_doc,     gp_clinic,   today_plus(0),  time(8,20),  "new",       "in_progress", "normal",   "Fever and body aches for 3 days"),
            (patients["SAGE/2023/000145"], gp_sched,   gp_doc,     gp_clinic,   today_plus(0),  time(8,40),  "followup",  "waiting",     "normal",   "CKD follow-up, creatinine review"),
            (patients["SAGE/2024/000089"], card_sched, cardio_doc, cardio_cl,   today_plus(0),  time(9,0),   "followup",  "waiting",     "normal",   "Chest pain evaluation post-discharge"),
            (patients["SAGE/2021/000007"], gp_sched,   gp_doc,     gp_clinic,   today_plus(0),  time(9,0),   "followup",  "waiting",     "elderly",  "Arthritis pain management — joint review"),
            (patients["SAGE/2025/000102"], gp_sched,   gp_doc,     gp_clinic,   today_plus(0),  time(9,20),  "new",       "scheduled",   "normal",   "Abdominal pain, nausea — 2 days"),
            (patients["SAGE/2026/000001"], gp_sched,   gp_doc,     gp_clinic,   today_plus(0),  time(10,0),  "new",       "scheduled",   "normal",   "First visit — general check-up"),
            (patients["SAGE/2024/000002"], anc_sched,  gp_doc,     anc_clinic,  today_plus(0),  time(10,20), "review",    "scheduled",   "pregnant", "Ante-natal visit — 28 weeks"),
            (patients["SAGE/2022/000033"], gp_sched,   gp_doc,     gp_clinic,   today_plus(0),  time(11,0),  "followup",  "scheduled",   "normal",   "Sickle cell post-admission review"),
            (patients["SAGE/2024/000210"], gp_sched,   gp_doc,     gp_clinic,   today_plus(0),  time(11,20), "followup",  "scheduled",   "normal",   "Post-anaphylaxis follow-up"),

            # ── tomorrow ───────────────────────────────────────────────────────
            (patients["SAGE/2024/000001"], gp_sched,   gp_doc,     gp_clinic,   today_plus(1),  time(8,0),   "followup",  "scheduled",   "normal",   "BP recheck after medication change"),
            (patients["SAGE/2024/000089"], card_sched, cardio_doc, cardio_cl,   today_plus(1),  time(9,0),   "procedure", "scheduled",   "normal",   "Coronary angiography prep"),
            (patients["SAGE/2023/000145"], gp_sched,   gp_doc,     gp_clinic,   today_plus(1),  time(9,40),  "followup",  "scheduled",   "normal",   "Nephrology review — oedema follow-up"),

            # ── in 2 days ──────────────────────────────────────────────────────
            (patients["SAGE/2025/000102"], gp_sched,   gp_doc,     gp_clinic,   today_plus(2),  time(8,0),   "review",    "scheduled",   "normal",   "Abdominal pain — results review"),
            (patients["SAGE/2026/000001"], gp_sched,   gp_doc,     gp_clinic,   today_plus(2),  time(8,40),  "followup",  "scheduled",   "normal",   "Post-registration review"),
            (patients["SAGE/2024/000002"], anc_sched,  gp_doc,     anc_clinic,  today_plus(2),  time(10,0),  "review",    "scheduled",   "pregnant", "28-week scan review — USS results"),

            # ── in 3–7 days ────────────────────────────────────────────────────
            (patients["SAGE/2021/000007"], gp_sched,   gp_doc,     gp_clinic,   today_plus(3),  time(9,0),   "followup",  "scheduled",   "elderly",  "Knee aspiration follow-up"),
            (patients["SAGE/2022/000033"], gp_sched,   gp_doc,     gp_clinic,   today_plus(4),  time(8,40),  "followup",  "scheduled",   "normal",   "Sickle cell haematology review"),
            (patients["SAGE/2024/000210"], gp_sched,   gp_doc,     gp_clinic,   today_plus(5),  time(10,0),  "followup",  "scheduled",   "normal",   "Allergy review — epipen education"),
            (patients["SAGE/2024/000089"], card_sched, cardio_doc, cardio_cl,   today_plus(7),  time(9,0),   "review",    "scheduled",   "normal",   "Post-angiogram results discussion"),

            # ── past (–1 day) ──────────────────────────────────────────────────
            (patients["SAGE/2024/000001"], ae_sched,   gp_doc,     ae_clinic,   today_plus(-1), time(14,0),  "new",       "completed",   "normal",   "Severe headache, BP 180/110"),
            (patients["SAGE/2025/000018"], gp_sched,   gp_doc,     gp_clinic,   today_plus(-1), time(8,20),  "new",       "no_show",     "normal",   "Follow-up — results review"),
            (patients["SAGE/2023/000145"], gp_sched,   gp_doc,     gp_clinic,   today_plus(-1), time(9,0),   "followup",  "completed",   "normal",   "Fluid balance review"),

            # ── past (–3 days) ─────────────────────────────────────────────────
            (patients["SAGE/2022/000033"], gp_sched,   gp_doc,     gp_clinic,   today_plus(-3), time(9,0),   "followup",  "completed",   "normal",   "Sickle cell crisis — initial assessment"),
            (patients["SAGE/2021/000007"], gp_sched,   gp_doc,     gp_clinic,   today_plus(-3), time(9,0),   "followup",  "completed",   "elderly",  "Pre-admission RA flare assessment"),
            (patients["SAGE/2024/000002"], anc_sched,  gp_doc,     anc_clinic,  today_plus(-3), time(10,0),  "review",    "completed",   "pregnant", "26-week ANC visit — all normal"),

            # ── past (–7 days) ─────────────────────────────────────────────────
            (patients["SAGE/2024/000001"], gp_sched,   gp_doc,     gp_clinic,   today_plus(-7), time(8,0),   "followup",  "completed",   "normal",   "BP and sugar check — monthly"),
            (patients["SAGE/2024/000210"], gp_sched,   gp_doc,     gp_clinic,   today_plus(-7), time(10,20), "new",       "completed",   "normal",   "Skin rash — possible food allergy"),
            (patients["SAGE/2025/000102"], gp_sched,   gp_doc,     gp_clinic,   today_plus(-7), time(9,20),  "new",       "completed",   "normal",   "Back pain, 2 weeks duration"),
            (patients["SAGE/2026/000001"], gp_sched,   gp_doc,     gp_clinic,   today_plus(-7), time(8,40),  "new",       "completed",   "normal",   "Registration and baseline bloods"),

            # ── past (–14 days) ────────────────────────────────────────────────
            (patients["SAGE/2023/000145"], gp_sched,   gp_doc,     gp_clinic,   today_plus(-14),time(8,40),  "followup",  "completed",   "normal",   "Renal function panel — worsening CKD"),
            (patients["SAGE/2024/000089"], card_sched, cardio_doc, cardio_cl,   today_plus(-14),time(9,0),   "new",       "completed",   "normal",   "Exertional chest pain, first cardiology visit"),
            (patients["SAGE/2022/000033"], gp_sched,   gp_doc,     gp_clinic,   today_plus(-14),time(9,20),  "followup",  "completed",   "normal",   "Sickle cell chronic care review"),
            (patients["SAGE/2024/000002"], anc_sched,  gp_doc,     anc_clinic,  today_plus(-14),time(10,0),  "review",    "completed",   "pregnant", "24-week ANC — growth scan review"),

            # ── past (–21 days) ────────────────────────────────────────────────
            (patients["SAGE/2024/000001"], gp_sched,   gp_doc,     gp_clinic,   today_plus(-21),time(8,0),   "followup",  "completed",   "normal",   "DM review — HbA1c result discussion"),
            (patients["SAGE/2021/000007"], gp_sched,   gp_doc,     gp_clinic,   today_plus(-21),time(9,0),   "followup",  "completed",   "elderly",  "Rheumatology review — prednisolone taper"),
            (patients["SAGE/2023/000145"], ae_sched,   gp_doc,     ae_clinic,   today_plus(-21),time(11,0),  "new",       "completed",   "normal",   "Hypertensive urgency — BP 190/115"),

            # ── additional patients — today ────────────────────────────────────
            (patients["SAGE/2024/000312"], gp_sched,   gp_doc,     gp_clinic,   today_plus(0),  time(7,40),  "new",       "checked_in",  "normal",   "Persistent cough and chest tightness — 1 week"),
            (patients["SAGE/2024/000313"], gp_sched,   gp_doc,     gp_clinic,   today_plus(0),  time(8,0),   "followup",  "in_progress", "elderly",  "Diabetes management — insulin dose review"),
            (patients["SAGE/2025/000220"], anc_sched,  gp_doc,     anc_clinic,  today_plus(0),  time(8,30),  "new",       "waiting",     "pregnant", "Booking visit — 12 weeks gestation"),
            (patients["SAGE/2023/000402"], gp_sched,   gp_doc,     gp_clinic,   today_plus(0),  time(8,40),  "followup",  "waiting",     "normal",   "Post-operative wound review — appendix"),
            (patients["SAGE/2026/000048"], gp_sched,   gp_doc,     gp_clinic,   today_plus(0),  time(9,0),   "new",       "waiting",     "normal",   "Severe lower back pain, radiating to leg"),
            (patients["SAGE/2025/000315"], card_sched, cardio_doc, cardio_cl,   today_plus(0),  time(9,20),  "new",       "scheduled",   "normal",   "Palpitations and dizziness — Holter review"),
            (patients["SAGE/2024/000555"], gp_sched,   gp_doc,     gp_clinic,   today_plus(0),  time(9,40),  "followup",  "scheduled",   "elderly",  "Osteoporosis review — bisphosphonate therapy"),
            (patients["SAGE/2026/000099"], gp_sched,   gp_doc,     gp_clinic,   today_plus(0),  time(10,0),  "new",       "scheduled",   "normal",   "Right knee swelling after sports injury"),
            (patients["SAGE/2023/000610"], gp_sched,   gp_doc,     gp_clinic,   today_plus(0),  time(10,20), "followup",  "scheduled",   "normal",   "Thyroid function review — on levothyroxine"),
            (patients["SAGE/2025/000440"], gp_sched,   gp_doc,     gp_clinic,   today_plus(0),  time(10,40), "new",       "scheduled",   "normal",   "Recurrent headaches — migraine assessment"),
            (patients["SAGE/2024/000312"], card_sched, cardio_doc, cardio_cl,   today_plus(0),  time(11,0),  "procedure", "scheduled",   "normal",   "ECG and echocardiogram — breathlessness"),
            (patients["SAGE/2023/000402"], ae_sched,   gp_doc,     ae_clinic,   today_plus(0),  time(11,20), "new",       "cancelled",   "normal",   "Acute abdominal pain — rescheduled"),
            (patients["SAGE/2026/000048"], anc_sched,  gp_doc,     anc_clinic,  today_plus(0),  time(11,40), "review",    "scheduled",   "pregnant", "Ante-natal check — 32 weeks"),

            # ── additional patients — tomorrow ─────────────────────────────────
            (patients["SAGE/2024/000312"], gp_sched,   gp_doc,     gp_clinic,   today_plus(1),  time(8,0),   "followup",  "scheduled",   "normal",   "Respiratory review — spirometry results"),
            (patients["SAGE/2024/000313"], gp_sched,   gp_doc,     gp_clinic,   today_plus(1),  time(8,20),  "followup",  "scheduled",   "elderly",  "Glycaemic control — HbA1c result"),
            (patients["SAGE/2025/000220"], gp_sched,   gp_doc,     gp_clinic,   today_plus(1),  time(8,40),  "new",       "scheduled",   "pregnant", "Hyperemesis gravidarum follow-up"),
            (patients["SAGE/2026/000099"], gp_sched,   gp_doc,     gp_clinic,   today_plus(1),  time(9,0),   "followup",  "scheduled",   "normal",   "MRI knee — result review"),
            (patients["SAGE/2025/000315"], card_sched, cardio_doc, cardio_cl,   today_plus(1),  time(9,20),  "followup",  "scheduled",   "normal",   "Holter result — cardiac arrhythmia workup"),
            (patients["SAGE/2025/000440"], gp_sched,   gp_doc,     gp_clinic,   today_plus(1),  time(10,0),  "followup",  "scheduled",   "normal",   "Migraine — triptan response assessment"),
            (patients["SAGE/2024/000555"], gp_sched,   gp_doc,     gp_clinic,   today_plus(1),  time(10,20), "followup",  "scheduled",   "elderly",  "Nutritional review and fall prevention"),
            (patients["SAGE/2023/000610"], anc_sched,  gp_doc,     anc_clinic,  today_plus(1),  time(11,0),  "review",    "scheduled",   "normal",   "Thyroid ultrasound — nodule review"),

            # ── additional patients — in 2 days ───────────────────────────────
            (patients["SAGE/2024/000313"], card_sched, cardio_doc, cardio_cl,   today_plus(2),  time(9,0),   "new",       "scheduled",   "normal",   "Diabetic cardiomyopathy screening"),
            (patients["SAGE/2023/000402"], gp_sched,   gp_doc,     gp_clinic,   today_plus(2),  time(9,20),  "followup",  "scheduled",   "normal",   "Post-op discharge review — wound healed"),
            (patients["SAGE/2025/000440"], gp_sched,   gp_doc,     gp_clinic,   today_plus(2),  time(10,0),  "review",    "scheduled",   "normal",   "Neurology referral — chronic migraine"),
            (patients["SAGE/2026/000048"], anc_sched,  gp_doc,     anc_clinic,  today_plus(2),  time(10,20), "review",    "scheduled",   "pregnant", "Growth scan review — fundal height concern"),

            # ── additional patients — past (–1 day) ───────────────────────────
            (patients["SAGE/2024/000312"], gp_sched,   gp_doc,     gp_clinic,   today_plus(-1), time(8,0),   "new",       "completed",   "normal",   "Initial chest assessment — peak flow done"),
            (patients["SAGE/2024/000313"], gp_sched,   gp_doc,     gp_clinic,   today_plus(-1), time(8,20),  "followup",  "completed",   "elderly",  "Insulin titration — fasting glucose review"),
            (patients["SAGE/2025/000220"], anc_sched,  gp_doc,     anc_clinic,  today_plus(-1), time(9,0),   "new",       "completed",   "pregnant", "First ANC booking bloods taken"),
            (patients["SAGE/2026/000099"], ae_sched,   gp_doc,     ae_clinic,   today_plus(-1), time(10,0),  "new",       "completed",   "normal",   "Acute knee trauma — X-ray ordered"),
            (patients["SAGE/2024/000555"], gp_sched,   gp_doc,     gp_clinic,   today_plus(-1), time(10,30), "followup",  "no_show",     "elderly",  "Calcium supplement review — did not attend"),
        ]

        appts = {}
        receptionist = staff.get("grace.eze@sagemed.ng")
        for (pat, sched, consult, clinic, appt_date, slot, atype, status, priority, reason) in appt_defs:
            key = f"{pat.hospital_number}-{appt_date}-{slot}"
            obj, _ = Appointment.objects.get_or_create(
                patient=pat,
                schedule=sched,
                date=appt_date,
                slot_time=slot,
                defaults={
                    "consultant": consult,
                    "clinic": clinic,
                    "appointment_type": atype,
                    "status": status,
                    "priority": priority,
                    "reason_for_visit": reason,
                    "booked_by": receptionist,
                },
            )
            appts[key] = obj

        self.stdout.write(f"  Appointments: {len(appt_defs)} records")
        return appts

    # ─── queue ────────────────────────────────────────────────────────────────

    def _seed_queue(self, patients, clinics, appts):
        from scheduling.models import QueueEntry, Appointment

        from accounts.models import User
        nurse = User.objects.filter(role="nurse").first()

        gp_clinic  = clinics["General Outpatient Clinic"]
        ae_clinic  = clinics["Emergency Department"]
        card_cl    = clinics["Cardiology Clinic"]
        anc_clinic = clinics["Ante-natal Clinic"]
        today      = date.today()

        # (patient, clinic, triage, status, is_walk_in, arrived_hour, arrived_min)
        queue_defs = [
            # ── General Outpatient Clinic ──────────────────────────────────────
            (patients["SAGE/2024/000001"], gp_clinic,  "green",  "with_doctor", False, 7, 55),
            (patients["SAGE/2025/000018"], gp_clinic,  "yellow", "with_doctor", False, 8, 10),
            (patients["SAGE/2024/000313"], gp_clinic,  "yellow", "with_doctor", False, 7, 50),
            (patients["SAGE/2023/000145"], gp_clinic,  "green",  "waiting",     False, 8, 30),
            (patients["SAGE/2021/000007"], gp_clinic,  "green",  "waiting",     False, 8, 45),
            (patients["SAGE/2023/000402"], gp_clinic,  "green",  "waiting",     False, 8, 35),
            (patients["SAGE/2026/000048"], gp_clinic,  "yellow", "waiting",     False, 8, 50),
            (patients["SAGE/2024/000555"], gp_clinic,  "green",  "waiting",     False, 9, 5),
            (patients["SAGE/2025/000102"], gp_clinic,  "green",  "waiting",     True,  9, 15),
            (patients["SAGE/2026/000099"], gp_clinic,  "green",  "waiting",     False, 9, 45),
            (patients["SAGE/2024/000312"], gp_clinic,  "green",  "waiting",     True,  7, 35),
            (patients["SAGE/2023/000610"], gp_clinic,  "green",  "waiting",     False, 10, 10),
            (patients["SAGE/2025/000440"], gp_clinic,  "green",  "waiting",     False, 10, 30),
            # ── Cardiology Clinic ──────────────────────────────────────────────
            (patients["SAGE/2024/000089"], card_cl,    "yellow", "with_doctor", False, 8, 55),
            (patients["SAGE/2025/000315"], card_cl,    "green",  "waiting",     False, 9, 10),
            # ── Ante-natal Clinic ──────────────────────────────────────────────
            (patients["SAGE/2025/000220"], anc_clinic, "green",  "with_doctor", False, 8, 20),
            (patients["SAGE/2026/000048"], anc_clinic, "green",  "waiting",     False, 11, 30),
            (patients["SAGE/2024/000002"], anc_clinic, "green",  "waiting",     False, 10, 15),
            # ── Emergency Department ───────────────────────────────────────────
            (patients["SAGE/2024/000210"], ae_clinic,  "red",    "completed",   True,  7, 20),
            (patients["SAGE/2026/000099"], ae_clinic,  "yellow", "waiting",     True,  9, 50),
            (patients["SAGE/2022/000033"], ae_clinic,  "red",    "with_doctor", True,  10, 5),
        ]

        queue_entries = {}
        for pat, clinic, triage, status, walk_in, ah, am in queue_defs:
            arrived = dt(0, ah, am)
            obj, _ = QueueEntry.objects.get_or_create(
                patient=pat, clinic=clinic, date=today,
                defaults={
                    "triage_level": triage,
                    "triage_nurse": nurse,
                    "triage_time": arrived,
                    "arrived_at": arrived,
                    "status": status,
                    "is_walk_in": walk_in,
                },
            )
            queue_entries[pat.hospital_number] = obj

        self.stdout.write(f"  Queue: {len(queue_defs)} entries for today")
        return queue_entries

    # ─── encounters ───────────────────────────────────────────────────────────

    def _seed_encounters(self, patients, staff, queue):
        from encounters.models import Encounter, Vitals, Diagnosis
        from prescriptions.models import Drug, Prescription

        doctor     = staff.get("chukwuemeka.okafor@sagemed.ng")
        resident   = staff.get("ngozi.adeyemi@sagemed.ng")
        nurse      = staff.get("fatima.usman@sagemed.ng")
        cardio_doc = staff.get("amina.bello@sagemed.ng")
        queue_p1   = queue.get("SAGE/2024/000001")

        encounters = {}

        # ── Patient 1 (Emeka) — today, signed encounter ──────────────────────
        enc1, _ = Encounter.objects.get_or_create(
            patient=patients["SAGE/2024/000001"],
            date_time=dt(0, 8, 5),
            defaults={
                "encounter_type": "opd",
                "location": "OPD Block A, Room 3",
                "attending": doctor,
                "appointment": queue_p1,
                "chief_complaint": "Headache and dizziness for 2 days. BP has been running high at home.",
                "history_of_presenting_illness": (
                    "Mr. Okonkwo is a 47-year-old known hypertensive and diabetic who presents with "
                    "a 2-day history of frontal headache and dizziness. BP at home (self-measured) "
                    "was 168/102 mmHg. He ran out of his Amlodipine 4 days ago. Denies chest pain, "
                    "shortness of breath, or blurring of vision. Last HbA1c was 7.8% two months ago."
                ),
                "review_of_systems": (
                    "CVS: No chest pain, no palpitations. RS: No SOB, no cough. "
                    "CNS: Headache ++, no focal deficits. GIT: Mild epigastric discomfort. "
                    "Renal: No dysuria, no haematuria."
                ),
                "examination_findings": (
                    "Alert, oriented, not pale/icteric/cyanosed. "
                    "BP: 164/98 mmHg (R arm, sitting). Pulse: 82 bpm, regular. "
                    "Temp: 37.1°C. SpO₂: 98%. Weight: 87 kg. "
                    "CVS: S1 S2 heard, no murmurs. RS: Clear. Abdomen: Soft, non-tender."
                ),
                "assessment": "1. Essential Hypertension — poorly controlled (medication non-adherence)\n2. T2DM — fair control (last HbA1c 7.8%)",
                "plan": (
                    "1. Resume Amlodipine 10mg OD (increased from 5mg)\n"
                    "2. Continue Metformin 500mg TDS with meals\n"
                    "3. Add Lisinopril 5mg OD\n"
                    "4. FBS, 2HPP, HbA1c, U&E, Creatinine — today\n"
                    "5. Lifestyle counselling: low-salt diet, exercise\n"
                    "6. Review in 4 weeks or earlier if BP > 160"
                ),
                "status": "signed",
                "signed_at": dt(0, 8, 55),
                "signed_by": doctor,
            },
        )
        encounters["SAGE/2024/000001-today"] = enc1

        Vitals.objects.get_or_create(
            encounter=enc1,
            defaults={
                "temperature": Decimal("37.1"),
                "bp_systolic": 164,
                "bp_diastolic": 98,
                "pulse": 82,
                "respiratory_rate": 18,
                "spo2": Decimal("98.0"),
                "weight": Decimal("87.0"),
                "height": Decimal("173.0"),
                "pain_score": 3,
                "recorded_by": nurse,
            },
        )

        for icd, desc, dtype in [
            ("I10",   "Essential Hypertension — poorly controlled", "primary"),
            ("E11.9", "Type 2 Diabetes Mellitus",                   "secondary"),
        ]:
            Diagnosis.objects.get_or_create(
                encounter=enc1, icd10_code=icd,
                defaults={"description": desc, "diagnosis_type": dtype, "clinician": doctor},
            )

        # Prescriptions for enc1
        for generic, strength, form, dose, route, freq, duration, qty in [
            ("Amlodipine",  "5mg",  "tablet", "10mg",  "oral", "od",  28,  28),
            ("Lisinopril",  "10mg", "tablet", "5mg",   "oral", "od",  28,  28),
            ("Metformin",   "500mg","tablet", "500mg", "oral", "tds", 28,  84),
        ]:
            drug = Drug.objects.filter(
                generic_name=generic, strength=strength, dosage_form=form
            ).first()
            if drug:
                Prescription.objects.get_or_create(
                    encounter=enc1, drug=drug,
                    defaults={
                        "patient": patients["SAGE/2024/000001"],
                        "dose": dose,
                        "route": route,
                        "frequency": freq,
                        "duration_days": duration,
                        "quantity": qty,
                        "status": "pending",
                        "prescriber": doctor,
                    },
                )

        # ── Patient 1 — past encounter (7 days ago) ───────────────────────────
        enc1b, _ = Encounter.objects.get_or_create(
            patient=patients["SAGE/2024/000001"],
            date_time=dt(-7, 8, 10),
            defaults={
                "encounter_type": "opd",
                "location": "OPD Block A, Room 3",
                "attending": doctor,
                "chief_complaint": "Routine BP and blood sugar review.",
                "examination_findings": "BP 148/92 mmHg. RBS 8.4 mmol/L. Weight 87.5 kg.",
                "assessment": "1. HTN — improving\n2. T2DM — fair control",
                "plan": "Continue current medications. Repeat HbA1c in 3 months.",
                "status": "signed",
                "signed_at": dt(-7, 8, 45),
                "signed_by": doctor,
            },
        )
        Vitals.objects.get_or_create(
            encounter=enc1b,
            defaults={
                "temperature": Decimal("36.9"),
                "bp_systolic": 148,
                "bp_diastolic": 92,
                "pulse": 78,
                "respiratory_rate": 16,
                "spo2": Decimal("99.0"),
                "weight": Decimal("87.5"),
                "height": Decimal("173.0"),
                "pain_score": 0,
                "recorded_by": nurse,
            },
        )

        # ── Patient 4 (Ngozi) — today, in-progress (malaria) ─────────────────
        enc4, _ = Encounter.objects.get_or_create(
            patient=patients["SAGE/2025/000018"],
            date_time=dt(0, 8, 25),
            defaults={
                "encounter_type": "opd",
                "location": "OPD Block A, Room 1",
                "attending": resident,
                "chief_complaint": "Fever, headache, chills for 3 days.",
                "history_of_presenting_illness": (
                    "Miss Eze is a 29-year-old student presenting with 3-day history of "
                    "fever (measured temp up to 39.5°C at home), severe frontal headache, "
                    "chills and rigors, body aches, and loss of appetite. No recent travel "
                    "outside Lagos. Lives in Surulere. No vomiting, no diarrhoea."
                ),
                "examination_findings": (
                    "Temp: 38.9°C, Pulse: 96 bpm, BP: 106/68. Pale conjunctivae (mild). "
                    "No jaundice. No hepatosplenomegaly. No neck stiffness."
                ),
                "assessment": "1. Malaria — likely (pending MP/RDT)\n2. Rule out typhoid fever",
                "plan": "Order MP RDT, FBC, Widal test. Start artemether-lumefantrine if confirmed. Paracetamol for fever.",
                "status": "draft",
            },
        )
        encounters["SAGE/2025/000018-today"] = enc4

        Vitals.objects.get_or_create(
            encounter=enc4,
            defaults={
                "temperature": Decimal("38.9"),
                "bp_systolic": 106,
                "bp_diastolic": 68,
                "pulse": 96,
                "respiratory_rate": 22,
                "spo2": Decimal("97.0"),
                "weight": Decimal("58.0"),
                "height": Decimal("163.0"),
                "pain_score": 6,
                "recorded_by": nurse,
            },
        )

        Diagnosis.objects.get_or_create(
            encounter=enc4, icd10_code="B54",
            defaults={
                "description": "Malaria (unspecified) — provisional",
                "diagnosis_type": "working",
                "clinician": resident,
            },
        )

        # ── Patient 3 (Musa) — past encounter 14 days ago ────────────────────
        enc3, _ = Encounter.objects.get_or_create(
            patient=patients["SAGE/2023/000145"],
            date_time=dt(-14, 8, 45),
            defaults={
                "encounter_type": "opd",
                "location": "OPD Block A, Room 2",
                "attending": doctor,
                "chief_complaint": "Fatigue, leg swelling, decreased urine output.",
                "examination_findings": (
                    "BP 162/100. Pitting oedema both ankles +++. "
                    "Weight 72 kg (up from 69 kg last visit). Pallor present."
                ),
                "assessment": "CKD Stage 3 — volume overload. HTN — poorly controlled.",
                "plan": "Increase Furosemide to 80mg BD. Add Spironolactone 25mg OD. Restrict fluid intake. Renal panel, FBC.",
                "status": "signed",
                "signed_at": dt(-14, 9, 30),
                "signed_by": doctor,
            },
        )
        encounters["SAGE/2023/000145-past"] = enc3

        Vitals.objects.get_or_create(
            encounter=enc3,
            defaults={
                "temperature": Decimal("36.8"),
                "bp_systolic": 162,
                "bp_diastolic": 100,
                "pulse": 88,
                "respiratory_rate": 18,
                "spo2": Decimal("96.0"),
                "weight": Decimal("72.0"),
                "height": Decimal("168.0"),
                "pain_score": 2,
                "recorded_by": nurse,
            },
        )

        # ── Patient 7 (Aisha) — A&E encounter today (anaphylaxis) ────────────
        enc7, _ = Encounter.objects.get_or_create(
            patient=patients["SAGE/2024/000210"],
            date_time=dt(0, 7, 35),
            defaults={
                "encounter_type": "ae",
                "location": "A&E Bay 2",
                "attending": doctor,
                "chief_complaint": "Anaphylactic reaction — accidental peanut ingestion.",
                "examination_findings": (
                    "BP 88/56, PR 118 bpm, SpO₂ 91% on air. "
                    "Generalised urticaria, lip and tongue angioedema. "
                    "Stridor present. Wheezing bilateral."
                ),
                "assessment": "Anaphylaxis — Grade III (severe). Known peanut allergy.",
                "plan": (
                    "IM Adrenaline 0.5mg given stat. IV access ×2. "
                    "IV Normal Saline 1L over 30 min. Hydrocortisone 200mg IV. "
                    "Chlorpheniramine 10mg IV. Nebulised Salbutamol. Monitor closely. "
                    "Observe 6 hours minimum."
                ),
                "status": "signed",
                "signed_at": dt(0, 8, 10),
                "signed_by": doctor,
            },
        )
        encounters["SAGE/2024/000210-today"] = enc7

        Vitals.objects.get_or_create(
            encounter=enc7,
            defaults={
                "temperature": Decimal("36.5"),
                "bp_systolic": 88,
                "bp_diastolic": 56,
                "pulse": 118,
                "respiratory_rate": 28,
                "spo2": Decimal("91.0"),
                "weight": Decimal("65.0"),
                "height": Decimal("162.0"),
                "pain_score": 7,
                "recorded_by": nurse,
            },
        )

        self.stdout.write(f"  Encounters: {len(encounters)} created")
        return encounters

    # ─── laboratory ───────────────────────────────────────────────────────────

    def _seed_lab(self, patients, encounters, staff):
        from laboratory.models import LabTest, LabOrder, LabResult

        doctor   = staff.get("chukwuemeka.okafor@sagemed.ng")
        resident = staff.get("ngozi.adeyemi@sagemed.ng")
        lab_tech = staff.get("ibrahim.musa@sagemed.ng")

        # Ensure lab tests exist
        test_defs = [
            ("FBC",    "Full Blood Count",          "FBC",             "blood", 4,   2500, "g/L,10⁹/L"),
            ("MP-RDT", "Malaria Parasite (RDT)",    "Malaria/Parasito", "blood", 1,   1500, ""),
            ("BMP",    "Basic Metabolic Panel",     "Chemistry",       "blood", 6,   5000, "mmol/L"),
            ("HBA1C",  "HbA1c",                    "Endocrine",       "blood", 24,  8000, "%"),
            ("CREAT",  "Serum Creatinine",          "Renal",           "blood", 6,   3000, "µmol/L"),
            ("UREA",   "Serum Urea",               "Renal",           "blood", 6,   2500, "mmol/L"),
            ("ELYTES", "Serum Electrolytes",        "Renal",           "blood", 6,   3500, "mmol/L"),
            ("RBS",    "Random Blood Sugar",        "Endocrine",       "blood", 1,   1000, "mmol/L"),
            ("WIDAL",  "Widal Test",               "Serology",        "blood", 8,   3000, ""),
            ("LFT",    "Liver Function Tests",      "Chemistry",       "blood", 8,   5000, "U/L"),
            ("LIPID",  "Lipid Profile",            "Chemistry",       "blood", 8,   5500, "mmol/L"),
            ("ECHO",   "Echocardiogram",            "Cardiology",      "blood", 48, 25000, ""),
            ("ECG",    "12-Lead ECG",              "Cardiology",      "blood", 1,   5000, ""),
            ("UA",     "Urinalysis",               "Urine chemistry", "urine", 2,   1500, ""),
        ]
        tests = {}
        for code, name, panel, sample, tat, price, units in test_defs:
            t, _ = LabTest.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "panel": panel,
                    "sample_type": sample,
                    "turnaround_hours": tat,
                    "price": Decimal(str(price)),
                    "units": units,
                    "is_active": True,
                },
            )
            tests[code] = t

        enc_p1 = encounters.get("SAGE/2024/000001-today")
        enc_p4 = encounters.get("SAGE/2025/000018-today")
        enc_p3 = encounters.get("SAGE/2023/000145-past")

        order_defs = [
            # (patient_hn, test_code, encounter, priority, status, barcode, days_offset)
            # Hassan Chukwu (HTN/DM) — today
            ("SAGE/2024/000001", "HBA1C",  enc_p1, "routine", "resulted",        "BC-240001-01", -7),
            ("SAGE/2024/000001", "CREAT",  enc_p1, "routine", "released",        "BC-240001-02",  0),
            ("SAGE/2024/000001", "ELYTES", enc_p1, "routine", "released",        "BC-240001-03",  0),
            ("SAGE/2024/000001", "RBS",    enc_p1, "routine", "released",        "BC-240001-04",  0),
            # Ngozi Eze (fever) — today, urgent
            ("SAGE/2025/000018", "MP-RDT", enc_p4, "urgent",  "sample_collected","BC-250018-01",  0),
            ("SAGE/2025/000018", "FBC",    enc_p4, "urgent",  "in_progress",     "BC-250018-02",  0),
            ("SAGE/2025/000018", "WIDAL",  enc_p4, "routine", "ordered",         "BC-250018-03",  0),
            # Musa Abdullahi (CKD) — past
            ("SAGE/2023/000145", "CREAT",  enc_p3, "routine", "released",        "BC-230145-01", -14),
            ("SAGE/2023/000145", "UREA",   enc_p3, "routine", "released",        "BC-230145-02", -14),
            ("SAGE/2023/000145", "ELYTES", enc_p3, "routine", "released",        "BC-230145-03", -14),
            ("SAGE/2023/000145", "FBC",    enc_p3, "routine", "released",        "BC-230145-04", -14),
            # Taiwo Adeyemi (cardiac) — today, urgent
            ("SAGE/2024/000089", "LIPID",  None,   "routine", "resulted",        "BC-240089-01",  0),
            ("SAGE/2024/000089", "ECG",    None,   "urgent",  "in_progress",     "BC-240089-02",  0),
            # Aisha Mohammed (A&E) — today STAT
            ("SAGE/2024/000210", "ELYTES", None,   "stat",    "resulted",        "BC-240210-01",  0),
            ("SAGE/2024/000210", "FBC",    None,   "stat",    "sample_collected","BC-240210-02",  0),
            # Chukwudi Nwosu (AE paediatric) — today urgent
            ("SAGE/2022/000033", "FBC",    None,   "urgent",  "in_progress",     "BC-220033-01",  0),
            ("SAGE/2022/000033", "CREAT",  None,   "urgent",  "ordered",         "BC-220033-02",  0),
            # Temitope Ogunleye (ANC) — today routine
            ("SAGE/2025/000220", "UA",     None,   "routine", "ordered",         "BC-250220-01",  0),
            ("SAGE/2025/000220", "FBC",    None,   "routine", "ordered",         "BC-250220-02",  0),
            # Oluseun Adesanya (cardiology) — today routine
            ("SAGE/2025/000315", "LIPID",  None,   "routine", "ordered",         "BC-250315-01",  0),
            # Adaeze Obiora — today
            ("SAGE/2024/000312", "HBA1C",  None,   "routine", "sample_collected","BC-240312-01",  0),
            # Yusuf Garba — today
            ("SAGE/2024/000313", "RBS",    None,   "routine", "ordered",         "BC-240313-01",  0),
        ]

        orders = {}
        for hn, code, enc, priority, status, barcode, day_off in order_defs:
            pat = patients.get(hn)
            test = tests.get(code)
            if not pat or not test:
                continue
            clinician = doctor if hn != "SAGE/2025/000018" else resident
            obj, _ = LabOrder.objects.get_or_create(
                barcode=barcode,
                defaults={
                    "patient": pat,
                    "encounter": enc,
                    "test": test,
                    "ordering_clinician": clinician,
                    "priority": priority,
                    "status": status,
                    "collected_at": dt(day_off, 8, 30) if status != "ordered" else None,
                    "collected_by": lab_tech if status != "ordered" else None,
                },
            )
            orders[barcode] = obj

        # Results for released/resulted orders
        # (barcode, value, unit, ref_low, ref_high, flag, is_critical, tech, verified, day_offset)
        result_defs = [
            # Hassan Chukwu
            ("BC-240001-01", "7.8",  "%",      "5.7",  "6.5",  "high",          False, lab_tech, False, -7),
            ("BC-240001-02", "102",  "µmol/L", "59",   "104",  "normal",        False, lab_tech, True,   0),
            ("BC-240001-03", "138",  "mmol/L", "136",  "145",  "normal",        False, lab_tech, True,   0),
            ("BC-240001-04", "10.2", "mmol/L", "4.4",  "7.8",  "high",          False, lab_tech, True,   0),
            # Musa Abdullahi (CKD — critical creatinine)
            ("BC-230145-01", "312",  "µmol/L", "59",   "104",  "critical_high", True,  lab_tech, True, -14),
            ("BC-230145-02", "18.4", "mmol/L", "2.5",  "6.7",  "high",          False, lab_tech, True, -14),
            ("BC-230145-03", "5.9",  "mmol/L", "3.5",  "5.0",  "high",          False, lab_tech, True, -14),
            ("BC-230145-04", "72",   "g/L",    "120",  "160",  "low",           False, lab_tech, True, -14),
            # Taiwo Adeyemi (lipid — awaiting verify)
            ("BC-240089-01", "6.2",  "mmol/L", "0",    "5.2",  "high",          False, lab_tech, False,  0),
            # Aisha Mohammed (A&E STAT — electrolytes critical, awaiting verify)
            ("BC-240210-01", "6.8",  "mmol/L", "3.5",  "5.0",  "critical_high", True,  lab_tech, False,  0),
        ]

        for barcode, value, unit, ref_low, ref_high, flag, is_crit, tech, verified, day_off in result_defs:
            order = orders.get(barcode)
            if not order:
                continue
            LabResult.objects.get_or_create(
                order=order,
                defaults={
                    "value": value,
                    "unit": unit,
                    "reference_low": ref_low,
                    "reference_high": ref_high,
                    "abnormal_flag": flag,
                    "is_critical": is_crit,
                    "technician": tech,
                    "verified_by": tech if verified else None,
                    "verified_at": dt(day_off, 14, 0) if verified else None,
                    "released_at": dt(day_off, 14, 30) if verified else None,
                },
            )

        self.stdout.write(f"  Lab: {len(test_defs)} tests, {len(order_defs)} orders")

    # ─── pharmacy / stock ─────────────────────────────────────────────────────

    def _seed_pharmacy(self, staff):
        from pharmacy.models import Store, DrugBatch, StockLevel
        from prescriptions.models import Drug

        pharmacist = staff.get("kelechi.nwachukwu@sagemed.ng")

        main_store, _ = Store.objects.get_or_create(
            name="Main Dispensary",
            defaults={"location": "Ground Floor, OPD Block", "is_main": True, "is_active": True},
        )
        ward_store, _ = Store.objects.get_or_create(
            name="Ward Pharmacy",
            defaults={"location": "1st Floor, Ward A", "is_main": False, "is_active": True},
        )

        stock_defs = [
            # (generic, strength, form, batch, expiry, qty_recv, qty_rem, cost, reorder, reorder_qty)
            ("Amlodipine",         "5mg",   "tablet", "AMD-5-240101", today_plus(365),  500, 320, Decimal("45"),  100, 300),
            ("Lisinopril",         "10mg",  "tablet", "LIS-10-24A",   today_plus(400),  400, 248, Decimal("38"),   80, 200),
            ("Metformin",          "500mg", "tablet", "MET-5-240315", today_plus(450),  1000, 730, Decimal("22"),  200, 500),
            ("Furosemide",         "40mg",  "tablet", "FUR-40-240201",today_plus(380),  300, 142, Decimal("35"),   60, 150),
            ("Omeprazole",         "20mg",  "capsule","OMP-20-24B",   today_plus(420),  500, 380, Decimal("28"),  100, 300),
            ("Paracetamol",        "500mg", "tablet", "PAR-5-240101", today_plus(365),  2000,1450, Decimal("12"),  400, 1000),
            ("Artemether/Lumefantrine","20/120mg","tablet","COA-20-24A",today_plus(300),200, 88,  Decimal("280"),  40, 100),
            ("Amoxicillin",        "500mg", "capsule","AMX-5-240201", today_plus(240),  600, 340, Decimal("30"),  120, 300),
            ("Ceftriaxone",        "1g",    "injection","CEF-1G-24A",  today_plus(280),  200, 134, Decimal("450"),  40, 100),
            ("Ciprofloxacin",      "500mg", "tablet", "CIP-5-240301", today_plus(330),  400, 210, Decimal("55"),   80, 200),
            ("Salbutamol",         "100mcg","inhaler", "SAL-100-24A", today_plus(350),  80,  45,  Decimal("620"),  20,  50),
            ("Prednisolone",       "5mg",   "tablet", "PRE-5-240201", today_plus(400),  300, 220, Decimal("25"),   60, 150),
            ("Insulin (Regular)",  "100IU/ml","injection","ACT-100-24A",today_plus(120), 50,  22,  Decimal("3200"), 10,  30),
            ("Metronidazole",      "400mg", "tablet", "MET-4-240201", today_plus(360),  500, 290, Decimal("18"),  100, 300),
        ]

        for generic, strength, form, batch_num, expiry, qty_r, qty_rem, cost, reorder, reorder_qty in stock_defs:
            drug = Drug.objects.filter(generic_name=generic, strength=strength, dosage_form=form).first()
            if not drug:
                continue

            batch, _ = DrugBatch.objects.get_or_create(
                drug=drug, batch_number=batch_num, store=main_store,
                defaults={
                    "expiry_date": expiry,
                    "quantity_received": qty_r,
                    "quantity_remaining": qty_rem,
                    "unit_cost": cost,
                    "supplier": "Emzor Pharmaceuticals Ltd",
                    "received_by": pharmacist,
                },
            )

            StockLevel.objects.update_or_create(
                drug=drug, store=main_store,
                defaults={
                    "quantity_on_hand": qty_rem,
                    "reorder_level": reorder,
                    "reorder_quantity": reorder_qty,
                },
            )

        self.stdout.write(f"  Pharmacy: {len(stock_defs)} drugs stocked")

    # ─── wards & beds ─────────────────────────────────────────────────────────

    def _seed_wards(self, staff):
        from admissions.models import Ward, Room, Bed

        doctor     = staff.get("chukwuemeka.okafor@sagemed.ng")
        cardio_doc = staff.get("amina.bello@sagemed.ng")

        ward_defs = [
            ("Male Medical Ward",     "general",   "1st Floor", doctor),
            ("Female Medical Ward",   "general",   "1st Floor", doctor),
            ("Cardiology Ward",       "specialty", "2nd Floor", cardio_doc),
            ("Children's Ward",       "paediatric","1st Floor", doctor),
            ("Private Ward",          "private",   "2nd Floor", doctor),
        ]
        wards = {}
        for name, wtype, floor, consult in ward_defs:
            w, _ = Ward.objects.update_or_create(
                name=name,
                defaults={"ward_type": wtype, "floor": floor, "consultant": consult, "is_active": True},
            )
            wards[name] = w

        # Rooms and beds
        beds = {}
        room_configs = {
            "Male Medical Ward": [
                ("Room A", ["A1","A2","A3","A4","A5","A6"]),
                ("Room B", ["B1","B2","B3","B4"]),
            ],
            "Female Medical Ward": [
                ("Room A", ["A1","A2","A3","A4","A5","A6"]),
                ("Room B", ["B1","B2","B3","B4"]),
            ],
            "Cardiology Ward": [
                ("CCU",   ["C1","C2","C3","C4"]),
                ("Room 1",["1A","1B","1C","1D"]),
            ],
            "Children's Ward": [
                ("Bay 1", ["P1","P2","P3","P4","P5","P6"]),
            ],
            "Private Ward": [
                ("Single Rooms", ["PR1","PR2","PR3","PR4"]),
            ],
        }

        for ward_name, rooms in room_configs.items():
            w = wards[ward_name]
            for room_name, bed_labels in rooms:
                room, _ = Room.objects.get_or_create(ward=w, name=room_name)
                for label in bed_labels:
                    bed, _ = Bed.objects.get_or_create(
                        room=room, label=label,
                        defaults={"status": "available"},
                    )
                    beds[f"{ward_name}-{room_name}-{label}"] = bed

        # Set varied bed statuses for the bed map UI
        status_map = {
            "Male Medical Ward-Room A-A1": "occupied",
            "Male Medical Ward-Room A-A2": "occupied",
            "Male Medical Ward-Room A-A3": "occupied",
            "Male Medical Ward-Room A-A4": "available",
            "Male Medical Ward-Room A-A5": "available",
            "Male Medical Ward-Room A-A6": "maintenance",
            "Male Medical Ward-Room B-B1": "occupied",
            "Male Medical Ward-Room B-B2": "available",
            "Male Medical Ward-Room B-B3": "available",
            "Male Medical Ward-Room B-B4": "available",
            "Female Medical Ward-Room A-A1": "occupied",
            "Female Medical Ward-Room A-A2": "occupied",
            "Female Medical Ward-Room A-A3": "available",
            "Female Medical Ward-Room A-A4": "available",
            "Female Medical Ward-Room A-A5": "available",
            "Female Medical Ward-Room A-A6": "available",
            "Cardiology Ward-CCU-C1": "occupied",
            "Cardiology Ward-CCU-C2": "available",
        }
        for key, status in status_map.items():
            bed = beds.get(key)
            if bed:
                Bed.objects.filter(pk=bed.pk).update(status=status)

        self.stdout.write(f"  Wards: {len(wards)} wards, {len(beds)} beds")
        return beds

    # ─── admissions ───────────────────────────────────────────────────────────

    def _seed_admissions(self, patients, beds, staff, encounters):
        from admissions.models import Admission, WardRound

        doctor   = staff.get("chukwuemeka.okafor@sagemed.ng")
        nurse    = staff.get("samuel.obi@sagemed.ng")

        bed_mma1 = beds.get("Male Medical Ward-Room A-A1")
        bed_mma2 = beds.get("Male Medical Ward-Room A-A2")
        bed_fma1 = beds.get("Female Medical Ward-Room A-A1")
        bed_ccu1 = beds.get("Cardiology Ward-CCU-C1")

        adm_defs = [
            # (hn, bed, admit_days, diagnosis, status)
            ("SAGE/2023/000145", bed_mma1, -5,  "CKD Stage 3 with fluid overload",               "active"),
            ("SAGE/2024/000089", bed_ccu1, -2,  "Unstable angina — rule out NSTEMI",             "active"),
            ("SAGE/2021/000007", bed_fma1, -3,  "Acute exacerbation of rheumatoid arthritis",    "active"),
            ("SAGE/2022/000033", bed_mma2, -8,  "Sickle cell crisis — vaso-occlusive",           "active"),
        ]

        admissions = {}
        for hn, bed, days, diag, status in adm_defs:
            if not bed:
                continue
            pat = patients.get(hn)
            if not pat:
                continue
            adm, _ = Admission.objects.get_or_create(
                patient=pat,
                bed=bed,
                status="active",
                defaults={
                    "admitting_doctor": doctor,
                    "diagnosis_on_admission": diag,
                    "admitted_at": dt(days, 10, 0),
                },
            )
            admissions[hn] = adm

            # Ward rounds
            round_texts = {
                "SAGE/2023/000145": [
                    ("Day 5 — Oedema improving. Weight down to 69 kg (from 72 kg on admission). "
                     "BP 148/92. Creatinine still elevated at 290 µmol/L. Continue Furosemide IV, "
                     "fluid restriction 1L/day.", 0),
                    ("Day 3 — Marked oedema. Urinary output 800ml/24h. Continuing IV diuresis.", -2),
                ],
                "SAGE/2024/000089": [
                    ("Day 2 — Chest pain free since last night. ECG: no new changes. "
                     "Troponin trending down. BP 132/82. Plan: Echo today, cardiology review.", 0),
                ],
                "SAGE/2021/000007": [
                    ("Day 3 — Joints less swollen. CRP down from 86 to 42. "
                     "Continue IV methylprednisolone. Physio started.", 0),
                ],
                "SAGE/2022/000033": [
                    ("Day 8 — Pain score 4/10 (improving from 9/10 on admission). "
                     "Hb 72 g/L, stable. Maintain IV fluids, analgesia.", 0),
                    ("Day 5 — Pain crisis ongoing. Morphine PCA effective. "
                     "FBC repeated — Hb 68 g/L. Transfusion considered.", -3),
                ],
            }
            for note_text, day_off in round_texts.get(hn, []):
                WardRound.objects.get_or_create(
                    admission=adm,
                    round_at=dt(day_off, 9, 0),
                    defaults={
                        "clinician": doctor,
                        "note": note_text,
                        "plan": "Continue current management. Review tomorrow.",
                    },
                )

        self.stdout.write(f"  Admissions: {len(admissions)} active")
        return admissions

    # ─── billing ──────────────────────────────────────────────────────────────

    def _seed_billing(self, patients, encounters, staff):
        from billing.models import Invoice, InvoiceItem, Payment, ServiceCatalogue

        cashier = staff.get("tunde.adewale@sagemed.ng")
        doctor  = staff.get("chukwuemeka.okafor@sagemed.ng")

        def get_svc(code):
            return ServiceCatalogue.objects.filter(code=code).first()

        inv_defs = [
            # (hn, enc_key, inv_num, status, date_offset, items, discount, paid)
            (
                "SAGE/2024/000001", "SAGE/2024/000001-today",
                "INV-2026-00423", "issued", 0,
                [("CONS-GP", 1, Decimal("3000")), ("LAB-HBA1C",1,Decimal("8000")),
                 ("LAB-RFT",1,Decimal("5000"))],
                Decimal("0"), Decimal("0"),
            ),
            (
                "SAGE/2025/000018", "SAGE/2025/000018-today",
                "INV-2026-00424", "paid", 0,
                [("CONS-GP",1,Decimal("3000")), ("LAB-MP",1,Decimal("1500")),
                 ("LAB-FBC",1,Decimal("2500"))],
                Decimal("0"), Decimal("7000"),
            ),
            (
                "SAGE/2023/000145", "SAGE/2023/000145-past",
                "INV-2026-00401", "partial", -14,
                [("CONS-GP",1,Decimal("3000")), ("LAB-RFT",1,Decimal("5000")),
                 ("LAB-FBC",1,Decimal("2500")), ("ADM-BED",5,Decimal("10000"))],
                Decimal("0"), Decimal("25000"),
            ),
            (
                "SAGE/2024/000089", None,
                "INV-2026-00425", "draft", 0,
                [("CONS-SPEC",1,Decimal("8000")), ("IMG-ECG",1,Decimal("5000"))],
                Decimal("0"), Decimal("0"),
            ),
            (
                "SAGE/2021/000007", None,
                "INV-2026-00415", "paid", -7,
                [("CONS-GP",1,Decimal("3000")), ("PROC-DRESS",2,Decimal("2500"))],
                Decimal("1000"), Decimal("7000"),
            ),
        ]

        for hn, enc_key, inv_num, status, day_off, items, discount, paid in inv_defs:
            pat = patients.get(hn)
            enc = encounters.get(enc_key) if enc_key else None
            if not pat:
                continue

            inv, _ = Invoice.objects.get_or_create(
                invoice_number=inv_num,
                defaults={
                    "patient": pat,
                    "encounter": enc,
                    "status": status,
                    "discount": discount,
                    "discount_reason": "Staff discount" if discount else "",
                },
            )

            subtotal = Decimal("0")
            for code, qty, unit_price in items:
                svc = get_svc(code)
                InvoiceItem.objects.get_or_create(
                    invoice=inv,
                    description=svc.name if svc else code,
                    defaults={
                        "service": svc,
                        "quantity": qty,
                        "unit_price": unit_price,
                        "total": unit_price * qty,
                    },
                )
                subtotal += unit_price * qty

            total = max(Decimal("0"), subtotal - discount)
            balance = max(Decimal("0"), total - paid)
            Invoice.objects.filter(pk=inv.pk).update(
                subtotal=subtotal, total=total, amount_paid=paid, balance=balance
            )

            if paid > 0:
                Payment.objects.get_or_create(
                    invoice=inv,
                    amount=paid,
                    defaults={
                        "mode": "cash" if paid < 10000 else "pos",
                        "cashier": cashier,
                        "reference": f"RCT-{inv_num}",
                    },
                )

        self.stdout.write(f"  Billing: {len(inv_defs)} invoices")

    # ─── surgery ──────────────────────────────────────────────────────────────

    def _seed_surgery(self, patients, staff, admissions):
        from surgery.models import Theatre, SurgeryBooking

        doctor     = staff.get("chukwuemeka.okafor@sagemed.ng")
        cardio_doc = staff.get("amina.bello@sagemed.ng")

        t1, _ = Theatre.objects.get_or_create(
            name="Theatre 1 (Main)",
            defaults={"location": "2nd Floor Surgical Suite", "is_active": True},
        )
        t2, _ = Theatre.objects.get_or_create(
            name="Theatre 2 (Day Case)",
            defaults={"location": "Ground Floor Day Surgery", "is_active": True},
        )

        booking_defs = [
            # (pat_hn, theatre, surgeon, anaest, proc, icd, sched_date, sched_time, dur, priority, status)
            ("SAGE/2022/000033", t1, doctor,     None,       "Splenectomy — SCD sequestration",
             "D57.1", today_plus(3),  time(8, 0),  120, "urgent",    "confirmed"),
            ("SAGE/2024/000089", t1, cardio_doc, doctor,    "Coronary Angiography",
             "I20.9", today_plus(1),  time(9, 0),   90, "urgent",    "confirmed"),
            ("SAGE/2021/000007", t2, doctor,     None,       "Knee Joint Aspiration",
             "M17.1", today_plus(0),  time(10,30),  45, "elective",  "scheduled"),
            ("SAGE/2024/000001", t2, doctor,     None,       "Circumcision (elective)",
             "Z41.2", today_plus(7),  time(9, 0),   30, "elective",  "scheduled"),
        ]

        for hn, theatre, surgeon, anaest, proc, icd, sched_date, sched_time, dur, priority, status in booking_defs:
            pat = patients.get(hn)
            if not pat:
                continue
            adm = admissions.get(hn)
            SurgeryBooking.objects.get_or_create(
                patient=pat,
                procedure_name=proc,
                scheduled_date=sched_date,
                defaults={
                    "theatre": theatre,
                    "lead_surgeon": surgeon,
                    "anaesthetist": anaest,
                    "icd10_code": icd,
                    "scheduled_time": sched_time,
                    "duration_minutes": dur,
                    "priority": priority,
                    "status": status,
                    "admission": adm,
                    "booked_by": surgeon,
                },
            )

        self.stdout.write("  Surgery: 2 theatres, 4 bookings")

    # ─── notifications ────────────────────────────────────────────────────────

    def _seed_notifications(self, patients):
        from notifications.models import Notification

        notif_defs = [
            ("SAGE/2024/000001", "sms",   "+2348051234501",
             "Appointment reminder: You have an appointment at SAGE Medical Center tomorrow at 08:00. "
             "Please arrive 15 min early. Reply STOP to opt out.",
             "appointment_reminder", "delivered"),
            ("SAGE/2024/000002", "sms",   "+2348051234502",
             "Your ante-natal appointment at SAGE Medical Center is confirmed for 01 May 2026 at 10:00. "
             "Please bring your ANC card. — SAGE Medical Center",
             "appointment_booked",   "sent"),
            ("SAGE/2025/000018", "email", "ngozi.eze@gmail.com",
             "Your lab results are now available. Please visit the laboratory or ask your doctor. "
             "— SAGE Medical Center",
             "lab_result_ready",     "delivered"),
            ("SAGE/2023/000145", "sms",   "+2348051234503",
             "Invoice INV-2026-00401 of ₦55,500 has been issued. Please make payment at the billing desk. "
             "— SAGE Medical Center",
             "invoice_issued",       "delivered"),
            ("SAGE/2024/000089", "sms",   "+2348051234505",
             "A payment of ₦13,000 has been received on your account at SAGE Medical Center. Thank you. "
             "Ref: RCT-INV-2026-00425",
             "payment_received",     "sent"),
        ]

        for hn, channel, recipient, body, event_type, status in notif_defs:
            pat = patients.get(hn)
            Notification.objects.get_or_create(
                patient=pat,
                recipient=recipient,
                event_type=event_type,
                defaults={
                    "channel": channel,
                    "body": body,
                    "status": status,
                    "sent_at": dt(-1, 18, 0),
                },
            )

        self.stdout.write(f"  Notifications: {len(notif_defs)} records")
