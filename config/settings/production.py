import pymysql

from .base import *  # noqa: F403

pymysql.install_as_MySQLdb()

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": config("DB_NAME"),  # noqa: F405
        "USER": config("DB_USER"),  # noqa: F405
        "PASSWORD": config("DB_PASSWORD"),  # noqa: F405
        "HOST": config("DB_HOST", default="localhost"),  # noqa: F405
        "PORT": config("DB_PORT", default="3306"),  # noqa: F405
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        "CONN_MAX_AGE": 60,
    },
    "replica": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": config("DB_NAME"),  # noqa: F405
        "USER": config("DB_REPLICA_USER", default=config("DB_USER")),  # noqa: F405
        "PASSWORD": config("DB_REPLICA_PASSWORD", default=config("DB_PASSWORD")),  # noqa: F405
        "HOST": config("DB_REPLICA_HOST", default=config("DB_HOST", default="localhost")),  # noqa: F405
        "PORT": config("DB_PORT", default="3306"),  # noqa: F405
        "OPTIONS": {
            "charset": "utf8mb4",
        },
        "CONN_MAX_AGE": 60,
        "TEST": {"MIRROR": "default"},
    },
}

# Security
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Email
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST")  # noqa: F405
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)  # noqa: F405
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config("EMAIL_HOST_USER")  # noqa: F405
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD")  # noqa: F405

# Sentry
import sentry_sdk  # noqa: E402
from decouple import config as _config  # noqa: E402

sentry_sdk.init(
    dsn=_config("SENTRY_DSN", default=""),
    traces_sample_rate=0.2,
    profiles_sample_rate=0.1,
)

# Django Q2
Q_CLUSTER = {
    "name": "sage_prod",
    "workers": 2,
    "timeout": 120,
    "retry": 360,
    "orm": "default",
    "bulk": 10,
}

INSTALLED_APPS += ["django_q"]  # noqa: F405

# Static / uploads
STATIC_ROOT = config("STATIC_ROOT", default=str(BASE_DIR / "public_html" / "static"))  # noqa: F405
MEDIA_ROOT = config("MEDIA_ROOT", default=str(BASE_DIR / "uploads"))  # noqa: F405
