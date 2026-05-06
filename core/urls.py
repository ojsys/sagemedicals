from django.urls import path

from core.views import DashboardView, LandingView, TutorialView

app_name = "core"

urlpatterns = [
    path("", LandingView.as_view(), name="landing"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("tutorial/", TutorialView.as_view(), name="tutorial"),
]
