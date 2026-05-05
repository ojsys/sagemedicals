from django.urls import path

from pharmacy import views

app_name = "pharmacy"

urlpatterns = [
    path("", views.PharmacyDashboardView.as_view(), name="dashboard"),
    path("stock/", views.StockLevelListView.as_view(), name="stock"),
    path("batches/", views.BatchListView.as_view(), name="batches"),
    path("dispense/<int:prescription_pk>/", views.DispenseView.as_view(), name="dispense"),
    path("receive/", views.GoodsReceiptCreateView.as_view(), name="receive"),
]
