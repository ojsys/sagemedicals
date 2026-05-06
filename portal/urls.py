from django.urls import path

from portal import views

app_name = "portal"

urlpatterns = [
    path("", views.PortalLoginView.as_view(), name="login"),
    path("register/", views.PortalRegisterView.as_view(), name="register"),
    path("logout/", views.portal_logout, name="logout"),
    path("dashboard/", views.portal_dashboard, name="dashboard"),
    path("appointments/", views.portal_appointments, name="appointments"),
    path("results/", views.portal_results, name="results"),
    path("bills/", views.portal_bills, name="bills"),
    path("feedback/<int:encounter_pk>/", views.portal_feedback, name="feedback"),
    path("antenatal/", views.portal_antenatal, name="antenatal"),
]
