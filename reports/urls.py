from django.urls import path
from django.views.generic import RedirectView

from reports import views

app_name = "reports"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="reports:operational"), name="index"),
    path("operational/", views.OperationalDashboardView.as_view(), name="operational"),
    path("financial/", views.FinancialDashboardView.as_view(), name="financial"),
    path("clinical/", views.ClinicalDashboardView.as_view(), name="clinical"),
    path("monthly/", views.MonthlyReturnView.as_view(), name="monthly"),
    path("claims/", views.ClaimsListView.as_view(), name="claims"),
    path("claims/new/", views.ClaimBatchCreateView.as_view(), name="claim_batch_new"),
    path("claims/<int:pk>/submit/", views.ClaimBatchSubmitView.as_view(), name="claim_batch_submit"),
]
