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

## Production (cPanel — sagemedicals.com)

**Domain**: `https://www.sagemedicals.com`  
**Entry point**: `passenger_wsgi.py` (Phusion Passenger)

### Deploy steps

```bash
# 1. In cPanel > Setup Python App — create app, note the Python version (3.14)
# 2. SSH into the server, activate the cPanel-managed venv:
source /home/<cpanel_user>/virtualenv/<app_path>/bin/activate

# 3. Install production deps
pip install -r requirements/production.txt

# 4. Create .env in the project root (see below)

# 5. Collect static files into public_html/static/
python manage.py collectstatic --noinput

# 6. Run migrations
python manage.py migrate

# 7. Create superuser
python manage.py createsuperuser

# 8. Restart app in cPanel > Setup Python App > Restart
```

### Production `.env`

```
SECRET_KEY=<long-random-string>
DEBUG=False
ALLOWED_HOSTS=sagemedicals.com,www.sagemedicals.com

# Database (cPanel MySQL)
DB_NAME=<cpanel_user>_sageemr
DB_USER=<cpanel_user>_sagedb
DB_PASSWORD=<db-password>
DB_HOST=localhost
DB_PORT=3306

# Email — cPanel SMTP
# Create noreply@sagemedicals.com in cPanel > Email Accounts first.
# EMAIL_HOST_USER and the address inside DEFAULT_FROM_EMAIL must be identical —
# cPanel rejects any MAIL FROM that doesn't match the authenticated account.
EMAIL_HOST=mail.sagemedicals.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
EMAIL_HOST_USER=noreply@sagemedicals.com
EMAIL_HOST_PASSWORD=<cpanel-email-password>
DEFAULT_FROM_EMAIL=SAGE Medical Center <noreply@sagemedicals.com>

# Hospital
HOSPITAL_PHONE=+234-XXX-XXXX
HOSPITAL_ADDRESS=Lagos, Nigeria

# Payments
PAYSTACK_SECRET_KEY=sk_live_...
PAYSTACK_PUBLIC_KEY=pk_live_...

# SMS (Termii)
SMS_API_KEY=
SMS_SENDER_ID=SAGE

# NHIA
NHIA_API_BASE_URL=
NHIA_API_KEY=

# Sentry (optional — leave blank to disable)
SENTRY_DSN=
```

### Static & media paths

| Purpose | Path on server |
|---|---|
| Static files (CSS/JS) | `public_html/static/` |
| Media uploads | `uploads/` |

> cPanel serves `public_html/` directly, so static assets are available at `https://www.sagemedicals.com/static/` without a separate web server config.

### cPanel cron — background tasks (django-q2)

Add in cPanel > Cron Jobs (run every minute):

```
* * * * * /home/<cpanel_user>/virtualenv/<app_path>/bin/python /home/<cpanel_user>/<app_path>/manage.py qcluster >> /home/<cpanel_user>/logs/qcluster.log 2>&1
```

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
