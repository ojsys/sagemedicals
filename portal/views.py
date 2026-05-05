from datetime import date

from django import forms as django_forms
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views import View

from core.forms import SmartSelectMixin
from portal.services import (
    PORTAL_SESSION_COOKIE,
    complete_otp_login,
    get_portal_session,
    portal_login_required,
    self_register,
    start_otp_login,
)


# ── Forms ─────────────────────────────────────────────────────

class PhoneForm(django_forms.Form):
    phone = django_forms.CharField(
        max_length=20,
        widget=django_forms.TextInput(attrs={
            "class": "form-control form-control-lg",
            "placeholder": "08012345678",
            "inputmode": "tel",
        }),
    )


class OTPForm(django_forms.Form):
    code = django_forms.CharField(
        max_length=6, min_length=6,
        widget=django_forms.TextInput(attrs={
            "class": "form-control form-control-lg text-center",
            "placeholder": "000000",
            "inputmode": "numeric",
            "autocomplete": "one-time-code",
        }),
    )


class SelfRegisterForm(django_forms.Form):
    first_name = django_forms.CharField(
        widget=django_forms.TextInput(attrs={"class": "form-control"})
    )
    last_name = django_forms.CharField(
        widget=django_forms.TextInput(attrs={"class": "form-control"})
    )
    date_of_birth = django_forms.DateField(
        widget=django_forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    sex = django_forms.ChoiceField(
        choices=[("M", "Male"), ("F", "Female")],
        widget=django_forms.Select(attrs={"class": "form-select"}),
    )


class AppointmentRequestForm(SmartSelectMixin, django_forms.Form):
    clinic = django_forms.ModelChoiceField(
        queryset=None,
        widget=django_forms.Select(attrs={"class": "form-select"}),
    )
    preferred_date = django_forms.DateField(
        widget=django_forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    preferred_time = django_forms.TimeField(
        required=False,
        widget=django_forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
    )
    reason = django_forms.CharField(
        widget=django_forms.Textarea(attrs={"rows": 3, "class": "form-control"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from scheduling.models import Clinic
        self.fields["clinic"].queryset = Clinic.objects.filter(is_active=True)


class FeedbackForm(django_forms.Form):
    rating = django_forms.ChoiceField(
        choices=[(i, str(i)) for i in range(1, 6)],
        widget=django_forms.RadioSelect(),
    )
    comments = django_forms.CharField(
        required=False,
        widget=django_forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
    )


# ── Auth views ────────────────────────────────────────────────

class PortalLoginView(View):
    template_name = "portal/login.html"

    def get(self, request):
        if get_portal_session(request):
            return redirect("portal:dashboard")
        return render(request, self.template_name, {"form": PhoneForm()})

    def post(self, request):
        form = PhoneForm(request.POST)
        if form.is_valid():
            try:
                phone = start_otp_login(form.cleaned_data["phone"])
                request.session["portal_otp_phone"] = phone
                return redirect("portal:verify")
            except ValueError as e:
                form.add_error("phone", str(e))
        return render(request, self.template_name, {"form": form})


class PortalVerifyView(View):
    template_name = "portal/verify.html"

    def get(self, request):
        if "portal_otp_phone" not in request.session:
            return redirect("portal:login")
        return render(request, self.template_name, {"form": OTPForm()})

    def post(self, request):
        phone = request.session.get("portal_otp_phone")
        if not phone:
            return redirect("portal:login")
        form = OTPForm(request.POST)
        if form.is_valid():
            try:
                session = complete_otp_login(
                    phone,
                    form.cleaned_data["code"],
                    ip=request.META.get("REMOTE_ADDR"),
                    ua=request.META.get("HTTP_USER_AGENT", ""),
                )
                del request.session["portal_otp_phone"]
                response = redirect("portal:dashboard")
                response.set_cookie(
                    PORTAL_SESSION_COOKIE, session.token,
                    max_age=3600, httponly=True, samesite="Lax",
                )
                return response
            except ValueError as e:
                form.add_error("code", str(e))
        return render(request, self.template_name, {"form": form})


class PortalRegisterView(View):
    template_name = "portal/register.html"

    def get(self, request):
        phone = request.session.get("portal_otp_phone", "")
        return render(request, self.template_name, {
            "form": SelfRegisterForm(), "phone": phone,
        })

    def post(self, request):
        phone = request.session.get("portal_otp_phone", "")
        # Explicitly check if phone is available and valid before proceeding
        if not phone:
            messages.error(request, "Your registration session has expired or is invalid. Please start again.")
            return redirect("portal:login")
        
        # Optionally, validate phone format early if not already done by start_otp_login for all cases
        # from patients.services import validate_nigerian_phone
        # try:
        #     phone = validate_nigerian_phone(phone)
        # except ValueError:
        #     messages.error(request, "Invalid phone number in session. Please start again.")
        #     return redirect("portal:login")

        form = SelfRegisterForm(request.POST)
        if form.is_valid():
            try:
                patient, created = self_register(
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"],
                    date_of_birth=form.cleaned_data["date_of_birth"],
                    sex=form.cleaned_data["sex"],
                    phone=phone,
                )
                msg = "Account created." if created else "Welcome back."
                messages.success(request, msg)
                return redirect("portal:login")
            except ValueError as e:
                form.add_error(None, str(e))
        return render(request, self.template_name, {"form": form, "phone": phone})


def portal_logout(request):
    from django.utils import timezone
    token = request.COOKIES.get(PORTAL_SESSION_COOKIE)
    if token:
        from portal.models import PortalSession
        PortalSession.objects.filter(token=token).update(expires_at=timezone.now())
    response = redirect("portal:login")
    response.delete_cookie(PORTAL_SESSION_COOKIE)
    return response


# ── Portal views (require session) ───────────────────────────

@portal_login_required
def portal_dashboard(request):
    patient = request.portal_patient
    from encounters.models import Encounter
    from scheduling.models import Appointment
    upcoming = Appointment.objects.filter(
        patient=patient,
        date__gte=date.today(),
        status__in=["scheduled", "checked_in"],
    ).order_by("date", "slot_time")[:5]
    recent_encounters = Encounter.objects.filter(
        patient=patient, status="signed"
    ).order_by("-date_time")[:5]
    return render(request, "portal/dashboard.html", {
        "patient": patient,
        "upcoming_appointments": upcoming,
        "recent_encounters": recent_encounters,
    })


@portal_login_required
def portal_appointments(request):
    patient = request.portal_patient
    from portal.models import PortalAppointmentRequest
    requests_qs = PortalAppointmentRequest.objects.filter(
        patient=patient
    ).order_by("-created_at")
    form = AppointmentRequestForm()
    if request.method == "POST":
        form = AppointmentRequestForm(request.POST)
        if form.is_valid():
            from portal.models import PortalAppointmentRequest
            PortalAppointmentRequest.objects.create(
                patient=patient,
                preferred_date=form.cleaned_data["preferred_date"],
                preferred_time=form.cleaned_data["preferred_time"],
                clinic=form.cleaned_data["clinic"],
                reason=form.cleaned_data["reason"],
            )
            messages.success(request, "Appointment request submitted. We will confirm shortly.")
            return redirect("portal:appointments")
    return render(request, "portal/appointments.html", {
        "patient": patient, "form": form, "requests": requests_qs,
    })


@portal_login_required
def portal_results(request):
    patient = request.portal_patient
    from laboratory.models import LabOrder
    results = (
        LabOrder.objects.filter(patient=patient, status="released")
        .select_related("test", "result")
        .order_by("-created_at")[:20]
    )
    return render(request, "portal/results.html", {
        "patient": patient, "results": results,
    })


@portal_login_required
def portal_bills(request):
    patient = request.portal_patient
    from billing.models import Invoice
    invoices = Invoice.objects.filter(
        patient=patient
    ).exclude(status="void").order_by("-created_at")[:20]
    return render(request, "portal/bills.html", {
        "patient": patient, "invoices": invoices,
    })


@portal_login_required
def portal_feedback(request, encounter_pk):
    from encounters.models import Encounter
    from portal.models import PortalFeedback
    patient = request.portal_patient
    encounter = Encounter.objects.filter(
        pk=encounter_pk, patient=patient, status="signed"
    ).first()
    if not encounter:
        return redirect("portal:dashboard")
    if hasattr(encounter, "feedback"):
        messages.info(request, "Feedback already submitted.")
        return redirect("portal:dashboard")
    form = FeedbackForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        PortalFeedback.objects.create(
            patient=patient,
            encounter=encounter,
            rating=form.cleaned_data["rating"],
            comments=form.cleaned_data["comments"],
        )
        messages.success(request, "Thank you for your feedback!")
        return redirect("portal:dashboard")
    return render(request, "portal/feedback.html", {
        "patient": patient, "encounter": encounter, "form": form,
    })
