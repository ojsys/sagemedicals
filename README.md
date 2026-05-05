# SAGE EMR

Electronic Medical Records system for **SAGE Medical Center**, built with Django 6 and MySQL (cPanel production).

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.14 · Django 6.0.4 |
| API | Django REST Framework 3.17 |
| Auth | django-allauth + django-otp (TOTP) |
| Database | SQLite (local) · MySQL via PyMySQL (production) |
| Admin | django-jazzmin |
| Background tasks | django-q2 |
| PDF generation | WeasyPrint · ReportLab |
| Hosting | cPanel (passenger_wsgi.py) |

---

## Apps

| App | Responsibility |
|---|---|
| `accounts` | Custom user model (email-based), roles, audit log, session timeout |
| `patients` | Registration, demographics, allergies, chronic conditions |
| `scheduling` | Clinics, appointments, queue management |
| `encounters` | SOAP notes, diagnoses (ICD-10), vitals signing |
| `prescriptions` | e-Prescribing, drug catalogue |
| `laboratory` | Lab orders, results, critical-value alerts |
| `pharmacy` | Dispensing (FEFO), drug stock, inventory |
| `admissions` | Wards, beds, inpatient admissions/discharges |
| `surgery` | Operating theatre bookings |
| `billing` | Invoices, payments, Paystack/Flutterwave integration |
| `integrations` | NHIA claims batching, payer management |
| `notifications` | In-app alerts, SMS (Termii) |
| `reports` | Operational, financial, and clinical dashboards; NHMIS monthly return |
| `portal` | Patient-facing portal |

---

## Local Setup

```bash
# 1. Clone and create virtualenv
python -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install -r requirements/local.txt

# 3. Configure environment
cp .env.example .env   # edit SECRET_KEY, DEBUG=True, etc.

# 4. Migrate and seed
python manage.py migrate
python manage.py seed_dev_data

# 5. Run
python manage.py runserver
```

### Minimum `.env`

```
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

---

## Production (cPanel)

- Entry point: `passenger_wsgi.py`
- Set `DJANGO_SETTINGS_MODULE=config.settings.production`
- Database: add `DATABASE_URL` or individual `DB_*` vars; PyMySQL is used (no `mysqlclient`)
- Static files: `python manage.py collectstatic` → `public_html/static/`
- Media uploads: `uploads/`

---

## Testing

```bash
pytest              # run all tests
pytest --cov=.      # with coverage
```

---

## Key Configuration

- **Time zone**: `Africa/Lagos`
- **Session timeout**: 15 min (clinical roles) · 60 min (patient portal)
- **Password policy**: minimum 12 characters
- **Hospital identity**: set `HOSPITAL_NAME`, `HOSPITAL_PHONE`, `HOSPITAL_ADDRESS` in `.env`
- **Payments**: `PAYSTACK_SECRET_KEY` / `FLUTTERWAVE_SECRET_KEY`
- **SMS**: `SMS_API_KEY` (Termii by default)
- **NHIA**: `NHIA_API_BASE_URL`, `NHIA_API_KEY`
