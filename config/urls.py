from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.views import health_check

admin.site.site_header = "SAGE Medical Center — EMR"
admin.site.site_title = "SAGE EMR Admin"
admin.site.index_title = "Administration"

urlpatterns = [
    path("health/", health_check, name="health"),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("me/", include("accounts.urls")),

    # Dashboard (root)
    path("", include("core.urls")),

    # App URL modules (stubbed — filled in per phase)
    path("", include("patients.urls")),
    path("scheduling/", include("scheduling.urls")),
    path("encounters/", include("encounters.urls")),
    path("prescriptions/", include("prescriptions.urls")),
    path("lab/", include("laboratory.urls")),
    path("billing/", include("billing.urls")),
    path("pharmacy/", include("pharmacy.urls")),
    path("admissions/", include("admissions.urls")),
    path("surgery/", include("surgery.urls")),
    path("portal/", include("portal.urls")),
    path("reports/", include("reports.urls")),
    path("notifications/", include("notifications.urls")),
    path("integrations/", include("integrations.urls")),

    # REST API
    path("api/v1/", include("portal.api_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
