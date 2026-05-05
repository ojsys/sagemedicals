from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.forms.models import model_to_dict

from .models import AuditLog


def _serialize(instance):
    try:
        data = model_to_dict(instance)
        # Convert non-serialisable types (e.g. dates) to strings
        return {k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
                for k, v in data.items()}
    except Exception:
        return {"id": str(instance.pk)}


def log_change(sender, instance, action, before=None):
    from core.models import BaseModel
    if not isinstance(instance, BaseModel):
        return
    # Skip AuditLog itself to avoid recursion
    if sender is AuditLog:
        return
    after = _serialize(instance)
    AuditLog.objects.create(
        user=getattr(instance, "_current_user", None),
        action=action,
        app_label=sender._meta.app_label,
        model_name=sender._meta.model_name,
        object_id=str(instance.pk),
        before=before,
        after=after,
    )


@receiver(post_save)
def on_save(sender, instance, created, **kwargs):
    action = AuditLog.ACTION_CREATE if created else AuditLog.ACTION_UPDATE
    log_change(sender, instance, action)


@receiver(post_delete)
def on_delete(sender, instance, **kwargs):
    log_change(sender, instance, AuditLog.ACTION_DELETE, before=_serialize(instance))
