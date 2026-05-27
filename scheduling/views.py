from django import forms as django_forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from accounts.models import Role, User
from patients.models import Patient
from scheduling.models import Appointment, Clinic, ClinicSchedule, QueueEntry


WEEKDAY_CHOICES = [
    (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"),
    (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
]


class AppointmentForm(django_forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ["patient", "schedule", "date", "slot_time", "appointment_type", "priority", "reason_for_visit"]
        widgets = {
            "date": django_forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "slot_time": django_forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "reason_for_visit": django_forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            if isinstance(f.widget, django_forms.Select):
                f.widget.attrs["class"] = "form-select"
            else:
                f.widget.attrs.setdefault("class", "form-control")
        self.fields["schedule"].queryset = ClinicSchedule.objects.filter(is_active=True).select_related("clinic", "consultant")


class ClinicScheduleForm(django_forms.ModelForm):
    working_days = django_forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        widget=django_forms.CheckboxSelectMultiple,
        help_text="Days this consultant runs this clinic.",
    )

    class Meta:
        model = ClinicSchedule
        fields = [
            "clinic", "consultant", "working_days",
            "start_time", "end_time", "slot_duration_minutes",
            "max_per_slot", "is_active",
        ]
        widgets = {
            "start_time": django_forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "end_time": django_forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Consultants = clinical staff who hold clinics (doctors, residents)
        self.fields["consultant"].queryset = User.objects.filter(
            role__in=[Role.DOCTOR, Role.RESIDENT], is_active=True
        ).order_by("first_name", "last_name")
        self.fields["clinic"].queryset = Clinic.objects.filter(is_active=True)
        for name, f in self.fields.items():
            if name == "working_days":
                continue
            if isinstance(f.widget, django_forms.Select):
                f.widget.attrs.setdefault("class", "form-select")
            elif isinstance(f.widget, django_forms.CheckboxInput):
                continue
            else:
                f.widget.attrs.setdefault("class", "form-control")
        # On edit, preselect the existing working_days
        if self.instance and self.instance.pk and self.instance.working_days:
            self.initial["working_days"] = [str(d) for d in self.instance.working_days]

    def clean_working_days(self):
        return [int(d) for d in self.cleaned_data["working_days"]]


class ClinicForm(django_forms.ModelForm):
    class Meta:
        model = Clinic
        fields = ["name", "department", "location", "is_active"]
        widgets = {
            "name": django_forms.TextInput(attrs={"placeholder": "e.g. General Outpatient Clinic"}),
            "department": django_forms.TextInput(attrs={"placeholder": "e.g. Internal Medicine"}),
            "location": django_forms.TextInput(attrs={"placeholder": "e.g. Block B, Room 12"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            if isinstance(f.widget, django_forms.CheckboxInput):
                continue
            f.widget.attrs.setdefault("class", "form-control")


class TriageForm(django_forms.ModelForm):
    class Meta:
        model = QueueEntry
        fields = ["triage_level", "triage_notes"]
        widgets = {"triage_notes": django_forms.Textarea(attrs={"rows": 2, "class": "form-control"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["triage_level"].widget.attrs["class"] = "form-select"


@method_decorator(login_required, name="dispatch")
class DailyQueueView(View):
    template_name = "scheduling/queue.html"

    def get(self, request):
        today = timezone.localdate()
        clinic_id = request.GET.get("clinic")
        clinics = Clinic.objects.filter(is_active=True)
        level_order = {QueueEntry.TriageLevel.RED: 0, QueueEntry.TriageLevel.YELLOW: 1, QueueEntry.TriageLevel.GREEN: 2}

        clinic = None
        if clinic_id:
            clinic = get_object_or_404(Clinic, pk=clinic_id)

        base_qs = (
            QueueEntry.objects.filter(date=today)
            .exclude(status=QueueEntry.QueueStatus.COMPLETED)
            .select_related("patient", "appointment", "clinic")
            .prefetch_related("patient__allergies")
        )
        if clinic:
            base_qs = base_qs.filter(clinic=clinic)

        queue = sorted(base_qs, key=lambda q: (level_order.get(q.triage_level, 3), q.arrived_at))

        # Stats
        all_today = QueueEntry.objects.filter(date=today).exclude(status=QueueEntry.QueueStatus.COMPLETED)
        if clinic:
            all_today = all_today.filter(clinic=clinic)

        waiting_count     = sum(1 for q in queue if q.status == QueueEntry.QueueStatus.WAITING)
        with_doctor_count = sum(1 for q in queue if q.status == QueueEntry.QueueStatus.WITH_DOCTOR)
        done_today        = QueueEntry.objects.filter(date=today, status=QueueEntry.QueueStatus.COMPLETED)
        if clinic:
            done_today = done_today.filter(clinic=clinic)

        return render(request, self.template_name, {
            "today": today,
            "clinics": clinics,
            "clinic": clinic,
            "queue": queue,
            "waiting_count": waiting_count,
            "with_doctor_count": with_doctor_count,
            "done_count": done_today.count(),
        })


@method_decorator(login_required, name="dispatch")
class AppointmentCreateView(View):
    template_name = "scheduling/book_appointment.html"

    def get(self, request):
        patient_pk = request.GET.get("patient")
        initial = {}
        patient = None
        if patient_pk:
            patient = get_object_or_404(Patient, pk=patient_pk)
            initial["patient"] = patient
        form = AppointmentForm(initial=initial)
        return render(request, self.template_name, {
            "form": form,
            "patient": patient,
            "schedule_count": ClinicSchedule.objects.filter(is_active=True).count(),
        })

    def post(self, request):
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appt = form.save(commit=False)
            appt.consultant = appt.schedule.consultant
            appt.clinic = appt.schedule.clinic
            appt.booked_by = request.user
            appt._current_user = request.user
            appt.save()
            # Auto check-in to queue if date is today
            today = timezone.localdate()
            if appt.date == today:
                QueueEntry.objects.create(
                    patient=appt.patient, appointment=appt,
                    clinic=appt.clinic, date=today,
                    triage_level=QueueEntry.TriageLevel.GREEN,
                )
            from django.contrib import messages
            messages.success(request, f"Appointment booked for {appt.date} at {appt.slot_time.strftime('%H:%M')}.")
            return redirect("patients:detail", pk=appt.patient.pk)
        return render(request, self.template_name, {"form": form})


@method_decorator(login_required, name="dispatch")
class CheckInView(View):
    def post(self, request, pk):
        appt = get_object_or_404(Appointment, pk=pk)
        today = timezone.localdate()
        entry, created = QueueEntry.objects.get_or_create(
            appointment=appt,
            defaults={
                "patient": appt.patient, "clinic": appt.clinic,
                "date": today, "triage_level": QueueEntry.TriageLevel.GREEN,
            }
        )
        appt.status = Appointment.Status.CHECKED_IN
        appt.save(update_fields=["status"])
        if request.headers.get("HX-Request"):
            return render(request, "scheduling/partials/queue_row.html", {"entry": entry})
        return redirect("scheduling:queue")


@method_decorator(login_required, name="dispatch")
class WalkInView(View):
    template_name = "scheduling/walkin.html"

    def get(self, request):
        clinics = Clinic.objects.filter(is_active=True)
        return render(request, self.template_name, {"clinics": clinics})

    def post(self, request):
        patient_pk = request.POST.get("patient")
        clinic_pk = request.POST.get("clinic")
        priority = request.POST.get("priority", QueueEntry.TriageLevel.GREEN)
        if not patient_pk:
            messages.error(request, "Please search for and select a patient before adding to the queue.")
            return render(request, self.template_name, {"clinics": Clinic.objects.filter(is_active=True)})
        patient = get_object_or_404(Patient, pk=patient_pk)
        clinic = get_object_or_404(Clinic, pk=clinic_pk)
        QueueEntry.objects.create(
            patient=patient, clinic=clinic, date=timezone.localdate(),
            triage_level=priority, is_walk_in=True, status=QueueEntry.QueueStatus.WAITING,
        )
        messages.success(request, f"{patient.full_name} added to queue.")
        return redirect("scheduling:queue")


@method_decorator(login_required, name="dispatch")
class TriageUpdateView(View):
    def post(self, request, pk):
        entry = get_object_or_404(QueueEntry, pk=pk)
        form = TriageForm(request.POST, instance=entry)
        if form.is_valid():
            e = form.save(commit=False)
            e.triage_nurse = request.user
            e.triage_time = timezone.now()
            e._current_user = request.user
            e.save()
        if request.headers.get("HX-Request"):
            return render(request, "scheduling/partials/queue_row.html", {"entry": entry})
        return redirect("scheduling:queue")


@method_decorator(login_required, name="dispatch")
class AppointmentListView(View):
    template_name = "scheduling/appointments.html"

    def get(self, request):
        from django.db.models import Count, Q
        today = timezone.localdate()

        # Date range filter
        date_str = request.GET.get("date", "")
        status_filter = request.GET.get("status", "")
        clinic_filter = request.GET.get("clinic", "")

        try:
            selected_date = django_forms.fields.DateField().clean(date_str) if date_str else today
        except Exception:
            selected_date = today

        qs = (
            Appointment.objects.filter(date=selected_date)
            .select_related("patient", "consultant", "clinic")
            .prefetch_related("patient__allergies")
            .order_by("slot_time")
        )

        if status_filter:
            qs = qs.filter(status=status_filter)
        if clinic_filter:
            qs = qs.filter(clinic_id=clinic_filter)

        clinics = Clinic.objects.filter(is_active=True)

        # Timeline grouped by hour slot
        slots = {}
        for appt in qs:
            hour_label = appt.slot_time.strftime("%H:%M")
            slots.setdefault(hour_label, []).append(appt)

        # Stats
        today_total   = Appointment.objects.filter(date=today).count()
        today_done    = Appointment.objects.filter(date=today, status="completed").count()
        today_waiting = Appointment.objects.filter(date=today, status__in=["scheduled","checked_in"]).count()
        upcoming      = Appointment.objects.filter(
            date__gt=today, status="scheduled"
        ).count()

        return render(request, self.template_name, {
            "appointments": qs,
            "slots": slots,
            "clinics": clinics,
            "selected_date": selected_date,
            "status_filter": status_filter,
            "clinic_filter": clinic_filter,
            "today": today,
            "today_total": today_total,
            "today_done": today_done,
            "today_waiting": today_waiting,
            "upcoming": upcoming,
            "status_choices": Appointment.Status.choices,
        })


# ── Clinic & Schedule Management ──────────────────────────────

@method_decorator(login_required, name="dispatch")
class ClinicScheduleListView(View):
    template_name = "scheduling/schedule_list.html"

    def get(self, request):
        weekday_labels = dict(WEEKDAY_CHOICES)
        schedules = list(
            ClinicSchedule.objects.select_related("clinic", "consultant")
            .order_by("clinic__name", "consultant__first_name")
        )
        for s in schedules:
            s.working_days_display = " · ".join(
                weekday_labels.get(int(d), str(d)) for d in (s.working_days or [])
            ) or "—"
        clinics = Clinic.objects.all().order_by("name")
        return render(request, self.template_name, {
            "schedules": schedules,
            "clinics": clinics,
        })


@method_decorator(login_required, name="dispatch")
class ClinicScheduleCreateView(View):
    template_name = "scheduling/schedule_form.html"

    def get(self, request):
        return render(request, self.template_name, {
            "form": ClinicScheduleForm(),
            "action": "New",
        })

    def post(self, request):
        form = ClinicScheduleForm(request.POST)
        if form.is_valid():
            sched = form.save(commit=False)
            sched._current_user = request.user
            sched.save()
            messages.success(request, f"Schedule saved: {sched}.")
            return redirect("scheduling:schedule_list")
        return render(request, self.template_name, {"form": form, "action": "New"})


@method_decorator(login_required, name="dispatch")
class ClinicScheduleEditView(View):
    template_name = "scheduling/schedule_form.html"

    def get(self, request, pk):
        sched = get_object_or_404(ClinicSchedule, pk=pk)
        return render(request, self.template_name, {
            "form": ClinicScheduleForm(instance=sched),
            "schedule": sched,
            "action": "Edit",
        })

    def post(self, request, pk):
        sched = get_object_or_404(ClinicSchedule, pk=pk)
        form = ClinicScheduleForm(request.POST, instance=sched)
        if form.is_valid():
            updated = form.save(commit=False)
            updated._current_user = request.user
            updated.save()
            messages.success(request, "Schedule updated.")
            return redirect("scheduling:schedule_list")
        return render(request, self.template_name, {"form": form, "schedule": sched, "action": "Edit"})


@method_decorator(login_required, name="dispatch")
class ClinicScheduleDeleteView(View):
    def post(self, request, pk):
        sched = get_object_or_404(ClinicSchedule, pk=pk)
        if sched.appointments.exists():
            messages.error(request, "Cannot delete: this schedule has existing appointments. Deactivate it instead.")
        else:
            label = str(sched)
            sched.delete()
            messages.success(request, f"Schedule deleted: {label}.")
        return redirect("scheduling:schedule_list")


@method_decorator(login_required, name="dispatch")
class ClinicCreateView(View):
    """Quick inline clinic creation from the schedule list page."""

    def post(self, request):
        form = ClinicForm(request.POST)
        if form.is_valid():
            clinic = form.save(commit=False)
            clinic._current_user = request.user
            clinic.save()
            messages.success(request, f"Clinic '{clinic.name}' created.")
        else:
            messages.error(request, "Please enter a clinic name.")
        return redirect("scheduling:schedule_list")
