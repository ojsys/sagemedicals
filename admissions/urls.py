from django.urls import path

from admissions import views

app_name = "admissions"

urlpatterns = [
    path("", views.WardMapView.as_view(), name="ward_map"),
    path("list/", views.AdmissionListView.as_view(), name="list"),
    path("admit/<int:patient_pk>/", views.AdmitPatientView.as_view(), name="admit"),
    path("<int:pk>/", views.AdmissionDetailView.as_view(), name="detail"),
    path("<int:pk>/transfer/", views.TransferBedView.as_view(), name="transfer"),
    path("<int:pk>/discharge/", views.DischargeView.as_view(), name="discharge"),
    path("<int:pk>/round/add/", views.WardRoundAddView.as_view(), name="round_add"),
    path("<int:pk>/mar/add/", views.MARAddView.as_view(), name="mar_add"),
]
