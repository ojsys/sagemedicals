import base64
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View


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
