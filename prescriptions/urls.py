from django.urls import path

from prescriptions import views

app_name = "prescriptions"

urlpatterns = [
    path("", views.PrescriptionListView.as_view(), name="list"),
    path("drug-search/", views.DrugSearchView.as_view(), name="drug_search"),
    path("encounter/<int:encounter_pk>/prescribe/", views.PrescriptionCreateView.as_view(), name="create"),
    path("<int:pk>/cancel/", views.PrescriptionCancelView.as_view(), name="cancel"),
]
