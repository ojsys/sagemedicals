from django.contrib import messages
from django.contrib.admin import helpers
from django.contrib.admin.utils import get_deleted_objects
from django.core.exceptions import PermissionDenied
from django.db import router, transaction
from django.db.models import PROTECT
from django.template.response import TemplateResponse


# ---------------------------------------------------------------------------
# Force-delete helpers
# ---------------------------------------------------------------------------

def _delete_protected_relations(obj, using, visited):
    key = (obj.__class__.__name__, obj.pk)
    if key in visited:
        return
    visited.add(key)
    for rel in obj._meta.related_objects:
        if rel.on_delete is PROTECT:
            qs = rel.related_model.objects.using(using).filter(**{rel.field.name: obj})
            for related_obj in qs.iterator():
                _delete_protected_relations(related_obj, using, visited)
            rel.related_model.objects.using(using).filter(**{rel.field.name: obj}).delete()


def force_delete(obj):
    """Delete obj, first removing any records that block it with on_delete=PROTECT."""
    using = router.db_for_write(obj.__class__)
    _delete_protected_relations(obj, using, set())
    obj.delete(using=using)


# ---------------------------------------------------------------------------
# Bulk-delete action (replaces the built-in delete_selected for superusers)
# ---------------------------------------------------------------------------

def _superuser_bulk_delete(modeladmin, request, queryset):
    if request.POST.get("confirmed") == "yes":
        count = queryset.count()
        with transaction.atomic():
            for obj in queryset:
                force_delete(obj)
        modeladmin.message_user(request, f"{count} record(s) permanently deleted.")
        return None  # redirect back to changelist

    # First pass — show confirmation
    context = {
        **modeladmin.admin_site.each_context(request),
        "title": "Delete selected objects",
        "queryset": queryset,
        "objects_name": str(modeladmin.model._meta.verbose_name_plural),
        "opts": modeladmin.model._meta,
        "app_label": modeladmin.model._meta.app_label,
        "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
    }
    return TemplateResponse(
        request,
        "admin/superuser_delete_selected_confirmation.html",
        context,
    )


_superuser_bulk_delete.short_description = "Delete selected objects"


# ---------------------------------------------------------------------------
# Mixin
# ---------------------------------------------------------------------------

class SuperuserForceDeleteMixin:
    """
    Add to any ModelAdmin to give superusers a working Delete button even
    when related objects use on_delete=PROTECT.

    Non-superusers fall through to the standard Django behaviour unchanged.
    """

    def get_actions(self, request):
        actions = super().get_actions(request)
        if request.user.is_superuser:
            actions["delete_selected"] = (
                _superuser_bulk_delete,
                "delete_selected",
                "Delete selected objects",
            )
        return actions

    def delete_view(self, request, object_id, extra_context=None):
        if not request.user.is_superuser:
            return super().delete_view(request, object_id, extra_context)

        if not self.has_delete_permission(request):
            raise PermissionDenied

        obj = self.get_object(request, object_id)
        if obj is None:
            return self._get_obj_does_not_exist_redirect(request, self.model._meta, object_id)

        if request.method == "POST":
            obj_display = str(obj)
            obj_id = obj.pk
            with transaction.atomic():
                force_delete(obj)
            self.message_user(request, f"'{obj_display}' has been permanently deleted.")
            return self.response_delete(request, obj_display, obj_id)

        deleted_objects, model_count, perms_needed, protected = get_deleted_objects(
            [obj], request, self.admin_site
        )

        context = {
            **self.admin_site.each_context(request),
            "title": f"Delete {self.model._meta.verbose_name}",
            "object_name": str(self.model._meta.verbose_name),
            "object": obj,
            "deleted_objects": deleted_objects,
            "model_count": model_count,
            "protected": protected,
            "opts": self.model._meta,
            "app_label": self.model._meta.app_label,
            "is_popup": False,
            "to_field": None,
            **(extra_context or {}),
        }
        return TemplateResponse(
            request,
            "admin/superuser_delete_confirmation.html",
            context,
        )

    def delete_queryset(self, request, queryset):
        if not request.user.is_superuser:
            return super().delete_queryset(request, queryset)
        with transaction.atomic():
            for obj in queryset:
                force_delete(obj)
