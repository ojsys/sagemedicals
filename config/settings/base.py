from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("SECRET_KEY")

DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

DJANGO_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
]

LOCAL_APPS = [
    "core",
    "accounts",
    "patients",
    "scheduling",
    "encounters",
    "orders",
    "prescriptions",
    "laboratory",
    "pharmacy",
    "billing",
    "admissions",
    "surgery",
    "portal",
    "notifications",
    "reports",
    "integrations",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "accounts.middleware.SessionTimeoutMiddleware",
    "accounts.middleware.AuditMiddleware",
    "accounts.middleware.RateLimitMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "public_html" / "static"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "uploads"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

# django-allauth
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_USER_MODEL_USERNAME_FIELD = None  # User model has no username field; uses email
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# Session
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}

# Email (overridden per environment)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@sagemedical.ng")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# django-otp — issuer name shown in authenticator apps (e.g. Google Authenticator)
OTP_TOTP_ISSUER = "SAGE Medical Center"

# Session timeout (seconds) — overridden per role in middleware
SESSION_COOKIE_AGE = 900  # 15 min default for clinical roles
PATIENT_PORTAL_SESSION_AGE = 3600  # 60 min for patients

# Hospital identity
HOSPITAL_NAME = "SAGE Medical Center"
HOSPITAL_CODE = "SAGE"
HOSPITAL_PHONE = config("HOSPITAL_PHONE", default="")
HOSPITAL_ADDRESS = config("HOSPITAL_ADDRESS", default="")

# Paystack
PAYSTACK_SECRET_KEY = config("PAYSTACK_SECRET_KEY", default="")
PAYSTACK_PUBLIC_KEY = config("PAYSTACK_PUBLIC_KEY", default="")

# Flutterwave
FLUTTERWAVE_SECRET_KEY = config("FLUTTERWAVE_SECRET_KEY", default="")
FLUTTERWAVE_PUBLIC_KEY = config("FLUTTERWAVE_PUBLIC_KEY", default="")

# SMS
SMS_PROVIDER = config("SMS_PROVIDER", default="termii")
SMS_API_KEY = config("SMS_API_KEY", default="")
SMS_SENDER_ID = config("SMS_SENDER_ID", default="SAGE")

# NHIA
NHIA_API_BASE_URL = config("NHIA_API_BASE_URL", default="")
NHIA_API_KEY = config("NHIA_API_KEY", default="")

# Cache — local-memory by default; override in production with Memcached/Redis
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "sage-default",
    }
}

# Structured logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "sage": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# ── Jazzmin admin theme ────────────────────────────────────────────────────────
JAZZMIN_SETTINGS = {
    # ── Branding ──────────────────────────────────────────────────────────────
    "site_title": "SAGE EMR",
    "site_header": "SAGE Medical Center",
    "site_brand": "SAGE.",
    "welcome_sign": "SAGE Medical Center — Administration",
    "copyright": "SAGE Medical Center",

    # ── Top navigation ────────────────────────────────────────────────────────
    "topmenu_links": [
        {"name": "EMR", "url": "/", "new_window": False, "icon": "fas fa-hospital"},
        {"name": "Patients", "url": "/patients/", "icon": "fas fa-users"},
        {"name": "Queue", "url": "/scheduling/queue/", "icon": "fas fa-list-ol"},
    ],

    # ── User menu (top-right) ──────────────────────────────────────────────────
    "usermenu_links": [
        {"name": "EMR Dashboard", "url": "/", "icon": "fas fa-tachometer-alt"},
    ],

    # ── Sidebar ───────────────────────────────────────────────────────────────
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],

    "order_with_respect_to": [
        "accounts",
        "patients",
        "scheduling",
        "encounters",
        "prescriptions",
        "laboratory",
        "pharmacy",
        "admissions",
        "surgery",
        "billing",
        "notifications",
        "reports",
        "integrations",
        "auth",
    ],

    "icons": {
        # Apps
        "accounts": "fas fa-user-shield",
        "patients": "fas fa-user-injured",
        "scheduling": "fas fa-calendar-alt",
        "encounters": "fas fa-stethoscope",
        "prescriptions": "fas fa-capsules",
        "laboratory": "fas fa-flask",
        "pharmacy": "fas fa-prescription-bottle-alt",
        "admissions": "fas fa-bed",
        "surgery": "fas fa-cut",
        "billing": "fas fa-file-invoice-dollar",
        "notifications": "fas fa-bell",
        "reports": "fas fa-chart-bar",
        "integrations": "fas fa-plug",
        "auth": "fas fa-lock",
        # Models
        "accounts.User": "fas fa-user-md",
        "patients.Patient": "fas fa-id-card",
        "patients.Allergy": "fas fa-allergies",
        "patients.ChronicCondition": "fas fa-heartbeat",
        "scheduling.Clinic": "fas fa-clinic-medical",
        "scheduling.Appointment": "fas fa-calendar-check",
        "scheduling.QueueEntry": "fas fa-list-ol",
        "encounters.Encounter": "fas fa-stethoscope",
        "prescriptions.Drug": "fas fa-pills",
        "prescriptions.Prescription": "fas fa-file-medical-alt",
        "laboratory.LabTest": "fas fa-vials",
        "laboratory.LabOrder": "fas fa-microscope",
        "pharmacy.DrugStock": "fas fa-boxes",
        "admissions.Ward": "fas fa-hospital",
        "admissions.Bed": "fas fa-bed",
        "admissions.Admission": "fas fa-procedures",
        "billing.Invoice": "fas fa-receipt",
        "surgery.OperatingTheatre": "fas fa-syringe",
        "surgery.SurgeryBooking": "fas fa-calendar-plus",
        "auth.Group": "fas fa-users-cog",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",

    # ── UI tweaks ─────────────────────────────────────────────────────────────
    "related_modal_active": True,
    "custom_css": None,
    "custom_js": None,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "auth.user": "collapsible",
        "auth.group": "vertical_tabs",
    },
    "language_chooser": False,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-dark",
    "accent": "accent-teal",
    "navbar": "navbar-dark",
    "no_navbar_border": True,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-teal",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}
