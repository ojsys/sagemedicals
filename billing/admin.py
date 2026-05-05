from django.contrib import admin

from billing.models import Invoice, InvoiceItem, Payment, PaystackTransaction, ServiceCatalogue


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0

class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ("received_at",)

@admin.register(ServiceCatalogue)
class ServiceCatalogueAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "self_pay_price", "nhia_price", "is_active")
    list_filter = ("category", "is_active")

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "patient", "total", "amount_paid", "balance", "status")
    list_filter = ("status",)
    inlines = [InvoiceItemInline, PaymentInline]
    readonly_fields = ("invoice_number",)

@admin.register(PaystackTransaction)
class PaystackTransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "invoice", "amount_naira", "status", "created_at", "verified_at")
    list_filter = ("status",)
    readonly_fields = ("reference", "amount_kobo", "authorization_url", "paystack_id",
                       "gateway_response", "verified_at", "created_at")
