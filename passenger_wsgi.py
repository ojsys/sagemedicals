import os
import sys

# Add virtualenv site-packages (adjust path to match cPanel 'Setup Python App' virtualenv)
VENV_PATH = os.path.join(os.path.dirname(__file__), "venv")
sys.path.insert(0, os.path.join(VENV_PATH, "lib", "python3.10", "site-packages"))
sys.path.insert(0, os.path.dirname(__file__))

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.production"

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
