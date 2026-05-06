import sentry_sdk
from decouple import config

from .base import *  # noqa: F403

DEBUG = False

# WhiteNoise serves static files directly from Django (no web-server config needed).
# Must come directly after SecurityMiddleware so it runs before session/auth.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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


# Email verification is set to "optional" until SMTP is confirmed working.
# Change back to "mandatory" once noreply@sagemedicals.com is verified in cPanel.
ACCOUNT_EMAIL_VERIFICATION = "optional"

ALLOWED_HOSTS = [
    "sagemedicals.com",
    "www.sagemedicals.com",
    # cPanel routes all vhosts on this server through Passenger; the mail
    # subdomain shares the same IP so its Host header arrives here too.
    "mail.sagemedicals.com",
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
            "init_command": (
                "SET sql_mode='STRICT_TRANS_TABLES',"
                " character_set_connection=utf8mb4,"
                " collation_connection=utf8mb4_unicode_ci"
            ),
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
# cPanel's SMTP server enforces that the MAIL FROM address matches the
# authenticated account. EMAIL_HOST_USER and DEFAULT_FROM_EMAIL must use
# the same email address, or the server returns 550 Unauthenticated.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="mail.sagemedicals.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="noreply@sagemedicals.com")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="SAGE Medical Center <noreply@sagemedicals.com>")  # noqa: F405
SERVER_EMAIL = EMAIL_HOST_USER  # server alerts use bare address, no display name

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

# ── Logging — rotating file logs under logs/ ─────────────────────────────────
LOGS_DIR = BASE_DIR / "logs"  # noqa: F405
LOGS_DIR.mkdir(exist_ok=True)

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
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "error.log",
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 10,
            "formatter": "verbose",
            "level": "ERROR",
        },
        "app_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "sage.log",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "error_file"],
        "level": "WARNING",
    },
    "loggers": {
        "django.request": {
            "handlers": ["console", "error_file"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["error_file"],
            "level": "ERROR",
            "propagate": False,
        },
        "sage": {
            "handlers": ["console", "app_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ── Sentry error tracking (optional — leave DSN blank to disable) ─────────────
sentry_sdk.init(
    dsn=config("SENTRY_DSN", default=""),
    traces_sample_rate=0.1,
    profiles_sample_rate=0.05,
)
