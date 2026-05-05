from django.urls import path

from laboratory import views

app_name = "laboratory"

from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="laboratory:worklist"), name="index"),
    path("worklist/", views.LabWorklistView.as_view(), name="worklist"),
    path("encounter/<int:encounter_pk>/order/", views.LabOrderCreateView.as_view(), name="order_create"),
    path("order/<int:pk>/", views.LabOrderDetailView.as_view(), name="order_detail"),
    path("order/<int:pk>/collect/", views.SampleCollectView.as_view(), name="collect"),
    path("order/<int:pk>/result/", views.LabResultEntryView.as_view(), name="result_entry"),
    path("order/<int:pk>/verify/", views.LabResultVerifyView.as_view(), name="result_verify"),
    path("order/<int:pk>/acknowledge/", views.CriticalAcknowledgeView.as_view(), name="acknowledge"),
    path("order/<int:pk>/pdf/", views.LabResultPDFView.as_view(), name="result_pdf"),
]
