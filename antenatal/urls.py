from django.urls import path

from . import views

app_name = "antenatal"

urlpatterns = [
    path("",                                       views.ANCListView.as_view(),             name="list"),
    path("new/",                                   views.ANCRecordCreateView.as_view(),     name="create"),
    path("patient-search/",                        views.anc_patient_search,                name="patient_search"),
    path("<int:pk>/",                              views.ANCDetailView.as_view(),           name="detail"),
    path("<int:pk>/edit/",                         views.ANCRecordEditView.as_view(),       name="edit"),
    path("<int:pk>/visit/add/",                    views.ANCVisitCreateView.as_view(),      name="visit_add"),
    path("<int:pk>/visit/<int:visit_pk>/edit/",    views.ANCVisitEditView.as_view(),        name="visit_edit"),
    path("<int:pk>/scan/add/",                     views.ObstetricScanCreateView.as_view(), name="scan_add"),
    path("<int:pk>/scan/<int:scan_pk>/edit/",      views.ObstetricScanEditView.as_view(),   name="scan_edit"),
]
