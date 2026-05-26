from django.urls import path

from scheduling import views

app_name = "scheduling"

urlpatterns = [
    path("", views.DailyQueueView.as_view(), name="queue"),
    path("appointments/", views.AppointmentListView.as_view(), name="appointments"),
    path("book/", views.AppointmentCreateView.as_view(), name="book"),
    path("walkin/", views.WalkInView.as_view(), name="walkin"),
    path("appointment/<int:pk>/checkin/", views.CheckInView.as_view(), name="checkin"),
    path("queue/<int:pk>/triage/", views.TriageUpdateView.as_view(), name="triage"),
    path("schedules/", views.ClinicScheduleListView.as_view(), name="schedule_list"),
    path("schedules/new/", views.ClinicScheduleCreateView.as_view(), name="schedule_create"),
    path("schedules/<int:pk>/edit/", views.ClinicScheduleEditView.as_view(), name="schedule_edit"),
    path("schedules/<int:pk>/delete/", views.ClinicScheduleDeleteView.as_view(), name="schedule_delete"),
    path("clinics/new/", views.ClinicCreateView.as_view(), name="clinic_create"),
]
