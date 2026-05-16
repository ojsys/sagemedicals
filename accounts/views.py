import base64
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from .forms import PasswordResetForm, StaffUserCreateForm, StaffUserUpdateForm
from .models import Role, User


def _get_user_totp_device(user):
    from django_otp.plugins.otp_totp.models import TOTPDevice
    return TOTPDevice.objects.filter(user=user, confirmed=True).first()


def _get_unconfirmed_device(user):
    from django_otp.plugins.otp_totp.models import TOTPDevice
    return TOTPDevice.objects.filter(user=user, confirmed=False).first()


def _totp_qr_png_b64(device):
    import qrcode
    img = qrcode.make(device.config_url, box_size=6, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@method_decorator(login_required, name="dispatch")
class ProfileView(View):
    template_name = "accounts/profile.html"

    def get(self, request):
        totp_device = _get_user_totp_device(request.user)
        return render(request, self.template_name, {
            "totp_device": totp_device,
            "otp_verified": getattr(request.user, "is_verified", lambda: False)(),
        })


@method_decorator(login_required, name="dispatch")
class TwoFactorSetupView(View):
    template_name = "accounts/2fa_setup.html"

    def get(self, request):
        if _get_user_totp_device(request.user):
            messages.info(request, "2FA is already active on your account.")
            return redirect("accounts:profile")
        from django_otp.plugins.otp_totp.models import TOTPDevice
        TOTPDevice.objects.filter(user=request.user, confirmed=False).delete()
        device = TOTPDevice.objects.create(
            user=request.user, name=request.user.email, confirmed=False,
        )
        return render(request, self.template_name, {
            "device": device,
            "qr_b64": _totp_qr_png_b64(device),
        })

    def post(self, request):
        device = _get_unconfirmed_device(request.user)
        if not device:
            return redirect("accounts:2fa_setup")
        code = request.POST.get("code", "").strip().replace(" ", "")
        if device.verify_token(code):
            device.confirmed = True
            device.save()
            messages.success(request, "Two-factor authentication is now active.")
            return redirect("accounts:profile")
        messages.error(request, "Invalid code — check your authenticator app.")
        return render(request, self.template_name, {
            "device": device,
            "qr_b64": _totp_qr_png_b64(device),
            "error": True,
        })


@method_decorator(login_required, name="dispatch")
class TwoFactorDisableView(View):
    template_name = "accounts/2fa_disable.html"

    def get(self, request):
        if not _get_user_totp_device(request.user):
            return redirect("accounts:profile")
        return render(request, self.template_name, {})

    def post(self, request):
        from django_otp.plugins.otp_totp.models import TOTPDevice
        TOTPDevice.objects.filter(user=request.user).delete()
        messages.success(request, "Two-factor authentication disabled.")
        return redirect("accounts:profile")


@method_decorator(login_required, name="dispatch")
class TwoFactorVerifyView(View):
    """Post-login TOTP verification step."""
    template_name = "accounts/2fa_verify.html"

    def _dashboard(self):
        from django.urls import reverse
        return reverse("core:dashboard")

    def get(self, request):
        if not _get_user_totp_device(request.user):
            return redirect(self._dashboard())
        if getattr(request.user, "is_verified", lambda: True)():
            return redirect(self._dashboard())
        return render(request, self.template_name, {})

    def post(self, request):
        device = _get_user_totp_device(request.user)
        if not device:
            return redirect(self._dashboard())
        code = request.POST.get("code", "").strip().replace(" ", "")
        if device.verify_token(code):
            from django_otp import login as otp_login
            otp_login(request, device)
            # Use the next param only when it's a non-empty absolute path
            next_url = request.POST.get("next", "").strip()
            if not next_url or not next_url.startswith("/"):
                next_url = self._dashboard()
            return redirect(next_url)
        messages.error(request, "Invalid code. Try again.")
        return render(request, self.template_name, {"error": True})


# ────────────────────────────────────────────────────────────────────────────
# Staff management (Super Admin / Lead Doctor)
# ────────────────────────────────────────────────────────────────────────────

class StaffManagerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Allow Super Admin (or platform superuser) and Lead Doctors only."""

    def test_func(self):
        u = self.request.user
        return bool(u.is_authenticated and getattr(u, "can_manage_staff", False))

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("You don't have permission to manage staff.")
        return super().handle_no_permission()


class StaffUserListView(StaffManagerRequiredMixin, View):
    template_name = "accounts/users/user_list.html"

    def get(self, request):
        q = request.GET.get("q", "").strip()
        role = request.GET.get("role", "").strip()
        status = request.GET.get("status", "").strip()

        users = User.objects.exclude(role=Role.PATIENT).order_by(
            "-is_active", "last_name", "first_name", "email"
        )

        if q:
            users = users.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
                | Q(phone__icontains=q)
                | Q(department__icontains=q)
            )
        if role:
            users = users.filter(role=role)
        if status == "active":
            users = users.filter(is_active=True)
        elif status == "inactive":
            users = users.filter(is_active=False)
        elif status == "lead":
            users = users.filter(is_lead_doctor=True)

        paginator = Paginator(users, 25)
        page = paginator.get_page(request.GET.get("page"))

        counts = {
            "total": User.objects.exclude(role=Role.PATIENT).count(),
            "active": User.objects.exclude(role=Role.PATIENT).filter(is_active=True).count(),
            "inactive": User.objects.exclude(role=Role.PATIENT).filter(is_active=False).count(),
            "lead": User.objects.filter(is_lead_doctor=True).count(),
        }

        return render(request, self.template_name, {
            "page_obj": page,
            "q": q,
            "role": role,
            "status": status,
            "roles": [(r.value, r.label) for r in Role if r != Role.PATIENT],
            "counts": counts,
        })


class StaffUserCreateView(StaffManagerRequiredMixin, View):
    template_name = "accounts/users/user_form.html"

    def get(self, request):
        form = StaffUserCreateForm(requesting_user=request.user)
        return render(request, self.template_name, {
            "form": form,
            "mode": "create",
        })

    def post(self, request):
        form = StaffUserCreateForm(request.POST, requesting_user=request.user)
        if form.is_valid():
            user = form.save(commit=False)
            user.password_changed_at = timezone.now()
            user.save()
            messages.success(
                request,
                f"{user.get_full_name() or user.email} has been added as {user.get_role_display()}.",
            )
            return redirect("accounts:user_list")
        return render(request, self.template_name, {
            "form": form,
            "mode": "create",
        })


class StaffUserUpdateView(StaffManagerRequiredMixin, View):
    template_name = "accounts/users/user_form.html"

    def _get_target(self, request, pk):
        target = get_object_or_404(User, pk=pk)
        # Non-superusers cannot edit a Super Admin
        if not request.user.is_superuser and (
            target.is_superuser or target.role == Role.SUPER_ADMIN
        ):
            raise PermissionDenied("Only the Super Admin can edit this user.")
        return target

    def get(self, request, pk):
        target = self._get_target(request, pk)
        form = StaffUserUpdateForm(instance=target, requesting_user=request.user)
        return render(request, self.template_name, {
            "form": form,
            "target": target,
            "mode": "edit",
        })

    def post(self, request, pk):
        target = self._get_target(request, pk)
        form = StaffUserUpdateForm(request.POST, instance=target, requesting_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Profile for {target.get_full_name() or target.email} updated.")
            return redirect("accounts:user_list")
        return render(request, self.template_name, {
            "form": form,
            "target": target,
            "mode": "edit",
        })


class StaffUserToggleActiveView(StaffManagerRequiredMixin, View):
    """POST-only — activate or deactivate a user."""

    def post(self, request, pk):
        target = get_object_or_404(User, pk=pk)
        if target.pk == request.user.pk:
            messages.error(request, "You cannot deactivate your own account.")
            return redirect("accounts:user_list")
        if not request.user.is_superuser and (
            target.is_superuser or target.role == Role.SUPER_ADMIN
        ):
            raise PermissionDenied("Only the Super Admin can change a Super Admin's status.")
        target.is_active = not target.is_active
        target.save(update_fields=["is_active"])
        state = "activated" if target.is_active else "deactivated"
        messages.success(request, f"{target.get_full_name() or target.email} has been {state}.")
        return redirect("accounts:user_list")


class StaffUserToggleLeadView(StaffManagerRequiredMixin, View):
    """POST-only — grant or revoke the Lead Doctor flag. Superuser only."""

    def post(self, request, pk):
        if not request.user.is_superuser:
            raise PermissionDenied("Only the Super Admin can grant Lead Doctor rights.")
        target = get_object_or_404(User, pk=pk)
        target.is_lead_doctor = not target.is_lead_doctor
        target.save(update_fields=["is_lead_doctor"])
        if target.is_lead_doctor:
            messages.success(
                request,
                f"{target.get_full_name() or target.email} can now manage staff users.",
            )
        else:
            messages.success(
                request,
                f"Lead Doctor rights revoked for {target.get_full_name() or target.email}.",
            )
        return redirect("accounts:user_list")


class StaffUserPasswordResetView(StaffManagerRequiredMixin, View):
    template_name = "accounts/users/user_password.html"

    def _get_target(self, request, pk):
        target = get_object_or_404(User, pk=pk)
        if not request.user.is_superuser and (
            target.is_superuser or target.role == Role.SUPER_ADMIN
        ):
            raise PermissionDenied("Only the Super Admin can reset this user's password.")
        return target

    def get(self, request, pk):
        target = self._get_target(request, pk)
        return render(request, self.template_name, {
            "form": PasswordResetForm(),
            "target": target,
        })

    def post(self, request, pk):
        target = self._get_target(request, pk)
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            target.set_password(form.cleaned_data["password1"])
            target.password_changed_at = timezone.now()
            target.failed_login_attempts = 0
            target.locked_until = None
            target.save(update_fields=[
                "password", "password_changed_at",
                "failed_login_attempts", "locked_until",
            ])
            messages.success(
                request,
                f"Password reset for {target.get_full_name() or target.email}. "
                "Share the new password with them through a secure channel.",
            )
            return redirect("accounts:user_list")
        return render(request, self.template_name, {
            "form": form,
            "target": target,
        })
