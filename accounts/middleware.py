from django.conf import settings
from django.contrib.auth import logout
from django.core.cache import cache
from django.http import HttpResponse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


class SessionTimeoutMiddleware(MiddlewareMixin):
    """Enforce role-based session timeouts."""

    def process_request(self, request):
        if not request.user.is_authenticated:
            return

        now = timezone.now().timestamp()
        last_activity = request.session.get("_last_activity")

        if last_activity:
            timeout = self._get_timeout(request.user)
            if now - last_activity > timeout:
                logout(request)
                return

        request.session["_last_activity"] = now

    def _get_timeout(self, user):
        from accounts.models import Role
        if user.role == Role.PATIENT:
            return settings.PATIENT_PORTAL_SESSION_AGE
        return settings.SESSION_COOKIE_AGE


class AuditMiddleware(MiddlewareMixin):
    """Attach the current request user to model instances so signals can log it."""

    def process_request(self, request):
        if request.user.is_authenticated:
            from core.models import BaseModel
            BaseModel._current_user = request.user


class RateLimitMiddleware(MiddlewareMixin):
    """
    Simple IP-based rate limiter for auth and portal endpoints.
    Throttles: /accounts/login/, /portal/, /portal/verify/
    Default: 20 requests / 60 seconds per IP. Returns 429 on breach.
    """

    RATE_LIMIT_PATHS = ("/accounts/login/", "/portal/", "/portal/verify/")
    MAX_REQUESTS = 20
    WINDOW_SECONDS = 60

    def process_request(self, request):
        if not any(request.path.startswith(p) for p in self.RATE_LIMIT_PATHS):
            return

        ip = self._get_ip(request)
        key = f"rl:{ip}:{request.path[:40]}"
        count = cache.get(key, 0)
        if count >= self.MAX_REQUESTS:
            return HttpResponse(
                "Too many requests. Please wait and try again.",
                status=429,
                content_type="text/plain",
            )
        cache.set(key, count + 1, timeout=self.WINDOW_SECONDS)

    @staticmethod
    def _get_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")
