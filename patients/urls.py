from django.urls import path
from django.views.generic import RedirectView

from patients import views

app_name = "patients"

urlpatterns = [
    path("home/", RedirectView.as_view(pattern_name="patients:search"), name="home"),
    path("patients/", views.PatientSearchView.as_view(), name="search"),
    path("patients/search/", views.PatientSearchView.as_view(), name="search_htmx"),
    path("patients/register/", views.PatientRegisterView.as_view(), name="register"),
    path("patients/check-duplicate/", views.DuplicateCheckView.as_view(), name="check_duplicate"),
    path("patients/<int:pk>/", views.PatientDetailView.as_view(), name="detail"),
    path("patients/<int:pk>/edit/", views.PatientUpdateView.as_view(), name="update"),
    path("patients/<int:pk>/allergies/add/", views.AllergyCreateView.as_view(), name="allergy_add"),
    path("patients/<int:pk>/allergies/<int:allergy_pk>/delete/", views.AllergyDeleteView.as_view(), name="allergy_delete"),
    path("patients/<int:pk>/conditions/add/", views.ConditionCreateView.as_view(), name="condition_add"),
]
