from django.urls import path

from encounters import views

app_name = "encounters"

urlpatterns = [
    path("", views.EncounterListView.as_view(), name="list"),
    path("patients/<int:patient_pk>/encounter/start/", views.EncounterCreateView.as_view(), name="create"),
    path("<int:pk>/", views.EncounterWorkspaceView.as_view(), name="workspace"),
    path("<int:pk>/sign/", views.EncounterSignView.as_view(), name="sign"),
    path("<int:pk>/vitals/", views.VitalsSaveView.as_view(), name="vitals_save"),
    path("<int:pk>/diagnosis/add/", views.DiagnosisAddView.as_view(), name="diagnosis_add"),
    path("<int:pk>/diagnosis/<int:diag_pk>/delete/", views.DiagnosisDeleteView.as_view(), name="diagnosis_delete"),
]
