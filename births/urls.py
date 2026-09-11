from django.urls import path

from . import views

app_name = "births"

urlpatterns = [
    path("",                          views.BirthListView.as_view(),           name="list"),
    path("new/",                      views.BirthCreateView.as_view(),         name="create"),
    path("<int:pk>/",                 views.BirthDetailView.as_view(),         name="detail"),
    path("<int:pk>/edit/",            views.BirthEditView.as_view(),           name="edit"),
    path("<int:pk>/certificate.pdf",  views.BirthCertificatePDFView.as_view(), name="certificate"),
]
