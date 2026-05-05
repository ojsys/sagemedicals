from django.conf import settings
from django.core.cache import cache
from django.db import models


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = models.Manager()

    class Meta:
        abstract = True

    @property
    def is_deleted(self):
        return self.deleted_at is not None


_SITE_SETTINGS_CACHE_KEY = "site_settings_obj"


class SiteSettings(models.Model):
    """Singleton — always pk=1. Edit via Django admin > Site Settings."""

    hospital_name = models.CharField(
        max_length=120,
        default="SAGE Medical Center",
        help_text="Full legal name, used in page titles, emails, and documents.",
    )
    short_name = models.CharField(
        max_length=30,
        default="SAGE",
        help_text="Abbreviated name shown in the sidebar brand mark (e.g. SAGE).",
    )
    tagline = models.CharField(
        max_length=100,
        blank=True,
        help_text="Sub-label under the brand mark (e.g. 'Medical Center'). Defaults to 'EMR' if blank.",
    )
    logo = models.ImageField(
        upload_to="site/",
        blank=True,
        help_text=(
            "Logo shown in the sidebar and patient portal header. "
            "Use a transparent PNG optimised for dark backgrounds (min 300 px wide)."
        ),
    )
    logo_on_light = models.ImageField(
        upload_to="site/",
        blank=True,
        verbose_name="Logo (for light backgrounds)",
        help_text=(
            "Full-colour logo for invoices, reports, and other printed documents. "
            "Leave blank to use the primary logo above."
        ),
    )
    favicon = models.ImageField(
        upload_to="site/",
        blank=True,
        help_text="Browser tab icon. Recommended: 32×32 or 64×64 PNG.",
    )
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True, help_text="Full mailing / physical address.")
    website = models.URLField(blank=True)
    nhia_code = models.CharField(
        "NHIA code", max_length=40, blank=True,
        help_text="NHIA facility/provider code printed on insurance claims.",
    )
    accreditation = models.CharField(
        max_length=100, blank=True,
        help_text="Accreditation body or certificate number (printed on documents).",
    )
    rc_number = models.CharField(
        "RC number", max_length=40, blank=True,
        help_text="CAC registration number.",
    )
    footer_note = models.CharField(
        max_length=220, blank=True,
        help_text="Short line shown in the footer of invoices and lab reports (e.g. hours, slogan).",
    )

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return self.hospital_name

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce singleton
        super().save(*args, **kwargs)
        cache.delete(_SITE_SETTINGS_CACHE_KEY)

    def delete(self, *args, **kwargs):
        pass  # prevent deletion

    @classmethod
    def get(cls):
        obj = cache.get(_SITE_SETTINGS_CACHE_KEY)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(_SITE_SETTINGS_CACHE_KEY, obj, 300)
        return obj

    @property
    def doc_logo(self):
        """Returns the best logo for light-background documents."""
        return self.logo_on_light or self.logo
