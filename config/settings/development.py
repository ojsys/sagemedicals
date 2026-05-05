from .base import *  # noqa: F403

DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Skip email verification in dev — accounts are admin-provisioned anyway
ACCOUNT_EMAIL_VERIFICATION = "none"

# Relax session timeout during local dev
SESSION_COOKIE_AGE = 86400

# Django Q2 (sync mode locally — no cron needed)
Q_CLUSTER = {
    "name": "sage_local",
    "workers": 1,
    "sync": True,
    "timeout": 60,
    "retry": 120,
    "orm": "default",
}

INSTALLED_APPS += ["django_q"]  # noqa: F405
