from django import forms as django_forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from core.forms import SmartSelectMixin
from surgery.models import SurgeryBooking, Theatre


class SurgeryBookingForm(SmartSelectMixin, django_forms.ModelForm):
    class Meta:
        model = SurgeryBooking
        fields = [
            "patient", "theatre", "lead_surgeon", "anaesthetist",
            "procedure_name", "icd10_code", "scheduled_date", "scheduled_time",
            "duration_minutes", "priority", "pre_op_notes",
        ]
        widgets = {
            "scheduled_date": django_forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "scheduled_time": django_forms.TimeInput(
                attrs={"type": "time", "class": "form-control"}
            ),
            "pre_op_notes": django_forms.Textarea(
                attrs={"rows": 3, "class": "form-control"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from accounts.models import User
        active_users = User.objects.filter(is_active=True).order_by("last_name")
        self.fields["theatre"].queryset = Theatre.objects.filter(is_active=True)
        self.fields["lead_surgeon"].queryset = active_users
        self.fields["anaesthetist"].queryset = active_users
        for name, f in self.fields.items():
            if isinstance(f.widget, django_forms.Select):
                f.widget.attrs.setdefault("class", "form-select")
            else:
                f.widget.attrs.setdefault("class", "form-control")


@method_decorator(login_required, name="dispatch")
class TheatreListView(View):
    template_name = "surgery/theatre_list.html"

    def get(self, request):
        import datetime as dt
        date_str = request.GET.get("date", str(timezone.localdate()))
        try:
            selected_date = dt.date.fromisoformat(date_str)
        except ValueError:
            selected_date = timezone.localdate()

        prev_date = selected_date - dt.timedelta(days=1)
        next_date = selected_date + dt.timedelta(days=1)

        theatres = list(Theatre.objects.filter(is_active=True).order_by("name"))

        all_today = (
            SurgeryBooking.objects.filter(scheduled_date=selected_date)
            .select_related("patient", "lead_surgeon", "anaesthetist", "theatre")
            .order_by("scheduled_time")
        )

        active_bookings = [b for b in all_today if b.status != SurgeryBooking.Status.CANCELLED]
        cancelled_today = sum(1 for b in all_today if b.status == SurgeryBooking.Status.CANCELLED)
        cases_today = len(active_bookings)
        avg_duration = (
            sum(b.duration_minutes for b in active_bookings) // cases_today
            if cases_today else 0
        )
        completed_today = sum(1 for b in active_bookings if b.status == SurgeryBooking.Status.COMPLETED)

        # Build OR grid: rows = sorted unique scheduled times, cols = theatres
        times = sorted({b.scheduled_time for b in active_bookings})
        theatre_index = {t.pk: i for i, t in enumerate(theatres)}
        booking_map = {}  # (time, theatre_pk) → booking
        for b in active_bookings:
            booking_map[(b.scheduled_time, b.theatre_id)] = b

        or_grid = []
        for t in times:
            cells = [booking_map.get((t, th.pk)) for th in theatres]
            or_grid.append({"time": t, "cells": cells})

        return render(request, self.template_name, {
            "theatres": theatres,
            "or_grid": or_grid,
            "selected_date": selected_date,
            "prev_date": prev_date,
            "next_date": next_date,
            "today": timezone.localdate(),
            "cases_today": cases_today,
            "cancelled_today": cancelled_today,
            "avg_duration": avg_duration,
            "completed_today": completed_today,
        })


@method_decorator(login_required, name="dispatch")
class SurgeryBookingCreateView(View):
    template_name = "surgery/book.html"

    def get(self, request):
        patient_pk = request.GET.get("patient")
        initial = {}
        patient = None
        if patient_pk:
            from patients.models import Patient
            patient = get_object_or_404(Patient, pk=patient_pk)
            initial["patient"] = patient
        form = SurgeryBookingForm(initial=initial)
        return render(request, self.template_name, {"form": form, "patient": patient})

    def post(self, request):
        form = SurgeryBookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.booked_by = request.user
            booking._current_user = request.user
            booking.save()
            messages.success(
                request,
                f"Surgery booked: {booking.procedure_name} on {booking.scheduled_date}.",
            )
            return redirect("surgery:detail", pk=booking.pk)
        return render(request, self.template_name, {"form": form})


@method_decorator(login_required, name="dispatch")
class SurgeryBookingDetailView(View):
    template_name = "surgery/detail.html"

    def get(self, request, pk):
        booking = get_object_or_404(SurgeryBooking, pk=pk)
        return render(request, self.template_name, {"booking": booking})


@method_decorator(login_required, name="dispatch")
class SurgeryStatusUpdateView(View):
    """Quick status transitions: confirm → in_progress → completed / postponed / cancelled."""

    def post(self, request, pk):
        booking = get_object_or_404(SurgeryBooking, pk=pk)
        new_status = request.POST.get("status")
        allowed = [s.value for s in SurgeryBooking.Status]
        if new_status not in allowed:
            messages.error(request, "Invalid status.")
            return redirect("surgery:detail", pk=pk)

        booking.status = new_status
        if new_status == SurgeryBooking.Status.IN_PROGRESS:
            booking.started_at = timezone.now()
        elif new_status == SurgeryBooking.Status.COMPLETED:
            booking.completed_at = timezone.now()
            post_op = request.POST.get("post_op_notes", "")
            if post_op:
                booking.post_op_notes = post_op
        booking._current_user = request.user
        booking.save()
        messages.success(request, f"Surgery status updated to {booking.get_status_display()}.")
        return redirect("surgery:detail", pk=pk)
