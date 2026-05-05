from django.urls import path

from billing import views

app_name = "billing"

urlpatterns = [
    path("", views.BillingListView.as_view(), name="list"),
    path("<int:pk>/", views.InvoiceDetailView.as_view(), name="invoice"),
    path("<int:pk>/pdf/", views.InvoicePDFView.as_view(), name="invoice_pdf"),
    path("<int:invoice_pk>/pay/", views.PaymentCreateView.as_view(), name="pay"),
    path("<int:pk>/paystack/initiate/", views.PaystackInitiateView.as_view(), name="paystack_initiate"),
    path("paystack/callback/", views.PaystackCallbackView.as_view(), name="paystack_callback"),
    path("paystack/webhook/", views.paystack_webhook, name="paystack_webhook"),
]
