import os
import sys

# Absolute path to the project root (same directory as this file).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# cPanel "Setup Python App" manages the virtualenv — its site-packages are
# already on sys.path via the Passenger wrapper. This block is a fallback
# for servers where that injection doesn't happen automatically.
PYTHON_VERSION = "python3.12"
VENV_SITE_PACKAGES = os.path.join(BASE_DIR, "venv", "lib", PYTHON_VERSION, "site-packages")

if os.path.isdir(VENV_SITE_PACKAGES):
    sys.path.insert(0, VENV_SITE_PACKAGES)

sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
