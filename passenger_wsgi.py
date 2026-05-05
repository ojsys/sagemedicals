import os
import sys

# Absolute path to the project root (same directory as this file).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# cPanel "Setup Python App" creates a virtualenv at <app_root>/venv.
# Adjust the python3.x folder to match the Python version cPanel assigned.
PYTHON_VERSION = "python3.14"
VENV_SITE_PACKAGES = os.path.join(BASE_DIR, "venv", "lib", PYTHON_VERSION, "site-packages")

if os.path.isdir(VENV_SITE_PACKAGES):
    sys.path.insert(0, VENV_SITE_PACKAGES)

sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
