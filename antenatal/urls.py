from django.urls import path

from . import views

app_name = "antenatal"

urlpatterns = [
    path("", views.ANCListView.as_view(), name="list"),
    path("<int:pk>/", views.ANCDetailView.as_view(), name="detail"),
]
