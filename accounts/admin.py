from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import messages
from django.contrib.admin.utils import get_deleted_objects
from django.core.exceptions import PermissionDenied
from django.db import router, transaction
from django.db.models import PROTECT
from django.template.response import TemplateResponse

from .models import AuditLog, User


def _force_delete_user(obj):
    """Delete a user even when related objects use on_delete=PROTECT.

    Deletes protected related records first, then removes the user.
    Wrapped in a transaction by the caller.
    """
    using = router.db_for_write(obj.__class__)
    for rel in obj._meta.related_objects:
        if rel.on_delete is PROTECT:
            rel.related_model.objects.using(using).filter(
                **{rel.field.name: obj}
            ).delete()
    obj.delete(using=using)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "get_full_name", "role", "department", "is_active", "date_joined")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name", "phone")
    ordering = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {"fields": ("first_name", "last_name", "phone")}),
        ("Role & Access", {"fields": ("role", "department", "delegate_to", "delegation_expires_at")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Security", {"fields": ("failed_login_attempts", "locked_until", "password_changed_at")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "role", "password1", "password2"),
        }),
    )
    actions = ["deactivate_users", "activate_users", "force_delete_users"]

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        if not request.user.is_superuser:
            actions.pop("force_delete_users", None)
        return actions

    def delete_view(self, request, object_id, extra_context=None):
        if not self.has_delete_permission(request):
            raise PermissionDenied

        obj = self.get_object(request, object_id)
        if obj is None:
            return self._get_obj_does_not_exist_redirect(request, self.model._meta, object_id)

        if request.method == "POST":
            email = obj.email
            action = request.POST.get("action")

            if action == "force_delete" and request.user.is_superuser:
                with transaction.atomic():
                    _force_delete_user(obj)
                self.message_user(
                    request,
                    f"User '{email}' and all related records have been permanently deleted.",
                    level=messages.WARNING,
                )
            else:
                obj.is_active = False
                obj.save(update_fields=["is_active"])
                self.message_user(
                    request,
                    f"User '{email}' has been deactivated. Their clinical records are preserved.",
                    level=messages.WARNING,
                )
            return self.response_delete(request, email, object_id)

        deleted_objects, model_count, perms_needed, protected = get_deleted_objects(
            [obj], request, self.admin_site
        )

        context = {
            **self.admin_site.each_context(request),
            "title": "Delete user",
            "object_name": str(self.model._meta.verbose_name),
            "object": obj,
            "deleted_objects": deleted_objects,
            "model_count": model_count,
            "protected": protected,
            "opts": self.model._meta,
            "app_label": self.model._meta.app_label,
            "is_popup": False,
            "to_field": None,
            "is_superuser": request.user.is_superuser,
            **(extra_context or {}),
        }
        return TemplateResponse(
            request,
            "admin/accounts/user/deactivate_confirmation.html",
            context,
        )

    def delete_queryset(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(
            request,
            f"{count} user(s) deactivated. Their clinical records are preserved.",
            level=messages.WARNING,
        )

    @admin.action(description="Deactivate selected users")
    def deactivate_users(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} user(s) deactivated.")

    @admin.action(description="Activate selected users")
    def activate_users(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} user(s) activated.")

    @admin.action(description="[Superadmin] Permanently delete selected users and all related records")
    def force_delete_users(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(request, "Only superadmins can permanently delete users.", level=messages.ERROR)
            return
        count = 0
        with transaction.atomic():
            for obj in queryset:
                _force_delete_user(obj)
                count += 1
        self.message_user(
            request,
            f"{count} user(s) and all related records permanently deleted.",
            level=messages.WARNING,
        )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user", "action", "model_name", "object_id", "ip_address")
    list_filter = ("action", "app_label")
    search_fields = ("user__email", "model_name", "object_id")
    readonly_fields = ("user", "action", "app_label", "model_name", "object_id", "before", "after",
                       "reason", "ip_address", "user_agent", "timestamp")
    ordering = ("-timestamp",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
