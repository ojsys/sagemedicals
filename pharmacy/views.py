from django import forms as django_forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from core.forms import SmartSelectMixin
from pharmacy.models import (
    Dispense,
    DrugBatch,
    GoodsReceipt,
    GoodsReceiptLine,
    Store,
)
from prescriptions.models import Prescription


class GoodsReceiptForm(SmartSelectMixin, django_forms.ModelForm):
    class Meta:
        model = GoodsReceipt
        fields = ["store", "supplier", "invoice_reference", "received_date", "notes"]
        widgets = {
            "received_date": django_forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "notes": django_forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, f in self.fields.items():
            if isinstance(f.widget, django_forms.Select):
                f.widget.attrs["class"] = "form-select"
            else:
                f.widget.attrs.setdefault("class", "form-control")


class GoodsReceiptLineForm(SmartSelectMixin, django_forms.ModelForm):
    class Meta:
        model = GoodsReceiptLine
        fields = ["drug", "batch_number", "expiry_date", "quantity_ordered", "quantity_received", "unit_cost"]
        widgets = {
            "expiry_date": django_forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from prescriptions.models import Drug
        self.fields["drug"].queryset = Drug.objects.filter(is_active=True).order_by("generic_name")
        for name, f in self.fields.items():
            if isinstance(f.widget, django_forms.Select):
                f.widget.attrs["class"] = "form-select"
            else:
                f.widget.attrs.setdefault("class", "form-control")


GoodsReceiptLineFormSet = django_forms.inlineformset_factory(
    GoodsReceipt, GoodsReceiptLine,
    form=GoodsReceiptLineForm,
    extra=1, can_delete=True,
)


@method_decorator(login_required, name="dispatch")
class PharmacyDashboardView(View):
    template_name = "pharmacy/dashboard.html"

    def get(self, request):
        from pharmacy.services import get_expiry_alerts, get_low_stock_alerts
        stores = Store.objects.filter(is_active=True)
        store_pk = request.GET.get("store")

        # Default to first active store if none chosen
        if store_pk:
            store = get_object_or_404(Store, pk=store_pk)
        else:
            store = stores.first()

        expiry_alerts = get_expiry_alerts(store) if store else []
        low_stock = get_low_stock_alerts(store) if store else []
        pending_dispenses = (
            Dispense.objects.filter(store=store, status=Dispense.Status.PENDING)
            .select_related("prescription__drug", "prescription__patient")
            .order_by("created_at")
        ) if store else Dispense.objects.none()

        # Stats across all stores for the header strip
        from pharmacy.models import StockLevel
        from django.utils import timezone
        today = timezone.localdate()
        import datetime
        near_expiry_count = DrugBatch.objects.filter(
            expiry_date__lte=today + datetime.timedelta(days=90),
            expiry_date__gte=today,
            quantity_remaining__gt=0
        ).count()
        low_stock_count = len(low_stock)

        return render(request, self.template_name, {
            "stores": stores,
            "store": store,
            "expiry_alerts": expiry_alerts,
            "low_stock": low_stock,
            "pending_dispenses": pending_dispenses,
            "today": today,
        })


@method_decorator(login_required, name="dispatch")
class DispenseView(View):
    template_name = "pharmacy/dispense.html"

    def get(self, request, prescription_pk):
        rx = get_object_or_404(Prescription, pk=prescription_pk, status=Prescription.Status.PENDING)
        stores = Store.objects.filter(is_active=True)
        return render(request, self.template_name, {"rx": rx, "stores": stores})

    def post(self, request, prescription_pk):
        rx = get_object_or_404(Prescription, pk=prescription_pk, status=Prescription.Status.PENDING)
        store_pk = request.POST.get("store")
        store = get_object_or_404(Store, pk=store_pk)

        from pharmacy.services import dispense_prescription
        try:
            dispense_prescription(rx, store, request.user)
            messages.success(request, f"Dispensed {rx.drug} × {rx.quantity} from {store}.")
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("pharmacy:dispense", prescription_pk=prescription_pk)

        return redirect("encounters:workspace", pk=rx.encounter.pk)


@method_decorator(login_required, name="dispatch")
class GoodsReceiptCreateView(View):
    template_name = "pharmacy/goods_receipt.html"

    def _drug_list(self):
        from prescriptions.models import Drug
        return Drug.objects.filter(is_active=True).order_by("generic_name")

    def get(self, request):
        form = GoodsReceiptForm()
        formset = GoodsReceiptLineFormSet()
        return render(request, self.template_name, {
            "form": form, "formset": formset, "drug_list": self._drug_list(),
        })

    def post(self, request):
        form = GoodsReceiptForm(request.POST)
        formset = GoodsReceiptLineFormSet(request.POST)
        drug_list = self._drug_list()
        if form.is_valid() and formset.is_valid():
            receipt = form.save(commit=False)
            receipt.received_by = request.user
            receipt._current_user = request.user
            receipt.save()
            formset.instance = receipt
            formset.save()
            from pharmacy.services import receive_goods
            try:
                receive_goods(receipt)
                messages.success(request, "Goods received and stock updated.")
            except ValueError as e:
                messages.error(request, str(e))
            return redirect("pharmacy:dashboard")
        return render(request, self.template_name, {
            "form": form, "formset": formset, "drug_list": drug_list,
        })


@method_decorator(login_required, name="dispatch")
class StockLevelListView(View):
    template_name = "pharmacy/stock_levels.html"

    def get(self, request):
        import datetime
        from pharmacy.models import StockLevel
        stores = Store.objects.filter(is_active=True)
        store_pk = request.GET.get("store")
        stock_filter = request.GET.get("filter", "")
        search = request.GET.get("q", "").strip()

        store = get_object_or_404(Store, pk=store_pk) if store_pk else stores.first()

        stock = (
            StockLevel.objects.filter(store=store)
            .select_related("drug")
            .order_by("drug__generic_name")
        ) if store else StockLevel.objects.none()

        today = datetime.date.today()
        soon = today + datetime.timedelta(days=30)

        # Attach batch info to each stock level
        stock_rows = []
        for sl in stock:
            batch = (
                DrugBatch.objects.filter(drug=sl.drug, store=store, quantity_remaining__gt=0)
                .order_by("expiry_date")
                .first()
            )
            days_to_expiry = (batch.expiry_date - today).days if batch else None
            expiring_soon = batch and batch.expiry_date <= soon
            out_of_stock = sl.quantity_on_hand == 0
            if search and search.lower() not in sl.drug.generic_name.lower():
                continue
            if stock_filter == "low" and not sl.needs_reorder:
                continue
            if stock_filter == "expiring" and not expiring_soon:
                continue
            if stock_filter == "out" and not out_of_stock:
                continue
            max_capacity = max(sl.reorder_level * 3, sl.quantity_on_hand, 1)
            fill_pct = min(100, int(sl.quantity_on_hand / max_capacity * 100))
            stock_rows.append({
                "sl": sl, "batch": batch,
                "days_to_expiry": days_to_expiry,
                "expiring_soon": expiring_soon,
                "out_of_stock": out_of_stock,
                "fill_pct": fill_pct,
            })

        total_skus = StockLevel.objects.filter(store=store).count() if store else 0
        low_count = sum(1 for r in stock_rows if r["sl"].needs_reorder)
        expiring_count = sum(1 for r in stock_rows if r["expiring_soon"])
        out_count = sum(1 for r in stock_rows if r["out_of_stock"])

        return render(request, self.template_name, {
            "stores": stores, "store": store, "stock_rows": stock_rows,
            "stock_filter": stock_filter, "search": search,
            "total_skus": total_skus, "low_count": low_count,
            "expiring_count": expiring_count, "out_count": out_count,
        })


@method_decorator(login_required, name="dispatch")
class BatchListView(View):
    template_name = "pharmacy/batches.html"

    def get(self, request):
        store_pk = request.GET.get("store")
        stores = Store.objects.filter(is_active=True)
        batches = DrugBatch.objects.none()
        store = None
        if store_pk:
            store = get_object_or_404(Store, pk=store_pk)
            batches = (
                DrugBatch.objects.filter(store=store, quantity_remaining__gt=0)
                .select_related("drug")
                .order_by("expiry_date")
            )
        return render(request, self.template_name, {
            "stores": stores, "store": store, "batches": batches,
            "today": timezone.localdate(),
        })
