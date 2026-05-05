import sentry_sdk
from decouple import config

from .base import *  # noqa: F403

DEBUG = False

ALLOWED_HOSTS = [
    "sagemedicals.com",
    "www.sagemedicals.com",
]

# Trust the SSL termination proxy cPanel puts in front of Phusion Passenger
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True

# HSTS — tell browsers to always use HTTPS for 1 year
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = [
    "https://sagemedicals.com",
    "https://www.sagemedicals.com",
]

# ── Database ──────────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        "CONN_MAX_AGE": 60,
    },
}

# ── Static & media ────────────────────────────────────────────────────────────
# Paths are derived from BASE_DIR — no env var needed.
# cPanel serves public_html/ as the document root, so static assets land at
# https://www.sagemedicals.com/static/ without any extra web-server config.
STATIC_ROOT = BASE_DIR / "public_html" / "static"  # noqa: F405
STATICFILES_DIRS = []  # source 'static/' dir doesn't need to exist in production  # noqa: F405
MEDIA_ROOT = BASE_DIR / "uploads"  # noqa: F405

# ── Email (cPanel SMTP) ───────────────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="mail.sagemedicals.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="noreply@sagemedicals.com")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="SAGE Medical Center <noreply@sagemedicals.com>")  # noqa: F405
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# ── Hospital identity ─────────────────────────────────────────────────────────
HOSPITAL_NAME = "SAGE Medical Center"  # noqa: F405
HOSPITAL_CODE = "SAGE"  # noqa: F405

# ── Django Q2 (background tasks via cPanel cron) ─────────────────────────────
Q_CLUSTER = {
    "name": "sage_prod",
    "workers": 2,
    "timeout": 120,
    "retry": 360,
    "orm": "default",
    "bulk": 10,
}

INSTALLED_APPS += ["django_q"]  # noqa: F405

# ── Sentry error tracking (optional — leave DSN blank to disable) ─────────────
sentry_sdk.init(
    dsn=config("SENTRY_DSN", default=""),
    traces_sample_rate=0.1,
    profiles_sample_rate=0.05,
)
