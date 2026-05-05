def site_settings(request):
    try:
        from core.models import SiteSettings
        return {"site_settings": SiteSettings.get()}
    except Exception:
        # Table may not exist before first migration — return safe defaults.
        from types import SimpleNamespace
        return {
            "site_settings": SimpleNamespace(
                hospital_name="SAGE Medical Center",
                short_name="SAGE",
                tagline="",
                logo=None,
                logo_on_light=None,
                favicon=None,
                doc_logo=None,
                phone="",
                email="",
                address="",
                website="",
                nhia_code="",
                accreditation="",
                rc_number="",
                footer_note="",
            )
        }
