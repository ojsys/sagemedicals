from django.contrib.auth import authenticate, login
from django import forms as django_forms
from django.views import View
from django.shortcuts import redirect, render
from django.contrib import messages
from django.conf import settings
from datetime import date

from core.forms import SmartSelectMixin
from portal.services import (
    PORTAL_SESSION_COOKIE,
    get_portal_session,
    portal_login_required,
    self_register,
)

# ── Forms ─────────────────────────────────────────────────────

class EmailLoginForm(django_forms.Form):
    email = django_forms.EmailField(
        widget=django_forms.EmailInput(attrs={
            "class": "form-control form-control-lg",
            "placeholder": "email@example.com",
            "inputmode": "email",
        }),
    )
    password = django_forms.CharField(
        widget=django_forms.PasswordInput(attrs={
            "class": "form-control form-control-lg",
            "placeholder": "Password",
        }),
    )

class EmailRegisterForm(django_forms.Form):
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
    email = django_forms.EmailField(
        widget=django_forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "email@example.com",
        }),
    )
    phone = django_forms.CharField(
        required=False,
        max_length=20,
        widget=django_forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "08012345678 (Optional)",
            "inputmode": "tel",
        }),
    )
    password = django_forms.CharField(
        widget=django_forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Password",
        }),
    )
    password_confirm = django_forms.CharField(
        widget=django_forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Confirm Password",
        }),
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error("password_confirm", "Passwords do not match")
        return cleaned_data


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
        return render(request, self.template_name, {"form": EmailLoginForm()})

    def post(self, request):
        form = EmailLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=email, password=password) # username is email for custom User

            if user is not None and user.is_active:
                login(request, user)
                # Now, create a PortalSession for the authenticated user
                from portal.models import PortalSession
                from patients.models import Patient
                from django.utils import timezone
                from datetime import timedelta

                # Ensure the user has a linked Patient profile
                try:
                    patient = Patient.objects.get(user=user, deleted_at__isnull=True)
                except Patient.DoesNotExist:
                    messages.error(request, "No patient profile linked to this account. Please contact support.")
                    return render(request, self.template_name, {"form": form})

                ttl = getattr(settings, "PATIENT_PORTAL_SESSION_AGE", 3600)
                session = PortalSession.objects.create(
                    patient=patient,
                    expires_at=timezone.now() + timedelta(seconds=ttl),
                    ip_address=request.META.get("REMOTE_ADDR"),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )
                response = redirect("portal:dashboard")
                response.set_cookie(
                    PORTAL_SESSION_COOKIE, session.token,
                    max_age=3600, httponly=True, samesite="Lax",
                )
                return response
            else:
                form.add_error(None, "Invalid login credentials.")
        return render(request, self.template_name, {"form": form})





class PortalRegisterView(View):
    template_name = "portal/register.html"

    def get(self, request):
        return render(request, self.template_name, {"form": EmailRegisterForm()})

    def post(self, request):
        form = EmailRegisterForm(request.POST)
        if form.is_valid():
            try:
                patient, created = self_register(
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"],
                    date_of_birth=form.cleaned_data["date_of_birth"],
                    sex=form.cleaned_data["sex"],
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password"],
                    phone=form.cleaned_data.get("phone", ""), # Phone is now optional
                )
                msg = "Account created. You can now log in." if created else "Welcome back."
                messages.success(request, msg)
                return redirect("portal:login")
            except ValueError as e:
                form.add_error(None, str(e))
        return render(request, self.template_name, {"form": form})


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
    anc_record = patient.active_anc_record
    return render(request, "portal/dashboard.html", {
        "patient": patient,
        "upcoming_appointments": upcoming,
        "recent_encounters": recent_encounters,
        "anc_record": anc_record,
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
def portal_antenatal(request):
    from datetime import timedelta
    patient = request.portal_patient
    record = patient.active_anc_record
    past_records = (
        patient.anc_records
        .filter(is_active=False)
        .prefetch_related("visits")
        .order_by("-edd")
    )

    schedule = []
    if record:
        lmp = record.lmp if record.lmp else (record.edd - timedelta(days=280))
        visits_list = list(record.visits.all())
        today = date.today()

        # Most recent visit's next_visit_date = the clinic's scheduled next appointment
        next_scheduled = None
        if visits_list:
            next_scheduled = visits_list[0].next_visit_date  # visits ordered -visit_date

        MILESTONES = [
            (8,  "Booking / Early Assessment"),
            (12, "First Trimester Review"),
            (16, "16-Week Check"),
            (20, "Anomaly Scan"),
            (24, "24-Week Check"),
            (28, "28-Week Check"),
            (32, "32-Week Check"),
            (34, "34-Week Check"),
            (36, "36-Week Check"),
            (38, "38-Week Check"),
            (40, "Term Assessment"),
        ]

        for ga_week, label in MILESTONES:
            target_date = lmp + timedelta(weeks=ga_week)
            matched_visit = None
            for v in visits_list:
                if abs((v.visit_date - target_date).days) <= 14:
                    matched_visit = v
                    break

            if matched_visit:
                status = "done"
            elif next_scheduled and abs((next_scheduled - target_date).days) <= 14:
                status = "scheduled"
            elif target_date < today:
                status = "overdue"
            else:
                status = "upcoming"

            schedule.append({
                "ga_week": ga_week,
                "label": label,
                "target_date": target_date,
                "visit": matched_visit,
                "status": status,
            })

    return render(request, "portal/antenatal.html", {
        "patient": patient,
        "record": record,
        "past_records": past_records,
        "schedule": schedule,
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
