import json
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View


def _parse_date_range(request, default_days=30):
    today = timezone.localdate()
    try:
        end = date.fromisoformat(request.GET.get("end", str(today)))
    except ValueError:
        end = today
    try:
        start = date.fromisoformat(
            request.GET.get("start", str(end - timedelta(days=default_days)))
        )
    except ValueError:
        start = end - timedelta(days=default_days)
    return start, end


@method_decorator(login_required, name="dispatch")
class OperationalDashboardView(View):
    template_name = "reports/operational.html"

    def get(self, request):
        from reports.services import bed_occupancy, daily_snapshot, encounter_volume
        snap = daily_snapshot()
        occupancy = bed_occupancy()
        start, end = _parse_date_range(request, default_days=14)
        volume = list(encounter_volume(start, end))
        volume_labels = [str(v["day"]) for v in volume]
        volume_data = [v["count"] for v in volume]
        return render(request, self.template_name, {
            "snap": snap,
            "occupancy": occupancy,
            "volume_labels": json.dumps(volume_labels),
            "volume_data": json.dumps(volume_data),
            "start": start,
            "end": end,
        })


@method_decorator(login_required, name="dispatch")
class FinancialDashboardView(View):
    template_name = "reports/financial.html"

    def get(self, request):
        from reports.services import (
            outstanding_invoices,
            revenue_by_service_category,
            revenue_summary,
        )
        start, end = _parse_date_range(request, default_days=30)
        rev = revenue_summary(start, end)
        by_category = list(revenue_by_service_category(start, end))
        outstanding = outstanding_invoices(limit=20)

        daily = rev["daily"]
        daily_labels = [str(d["day"]) for d in daily]
        daily_data = [float(d["total"]) for d in daily]

        return render(request, self.template_name, {
            "start": start,
            "end": end,
            "revenue": rev,
            "by_category": by_category,
            "outstanding": outstanding,
            "daily_labels": json.dumps(daily_labels),
            "daily_data": json.dumps(daily_data),
        })


@method_decorator(login_required, name="dispatch")
class ClinicalDashboardView(View):
    template_name = "reports/clinical.html"

    def get(self, request):
        from reports.services import (
            encounter_volume,
            lab_turnaround,
            top_diagnoses,
            top_drugs_prescribed,
        )
        start, end = _parse_date_range(request, default_days=30)
        diagnoses = list(top_diagnoses(start, end))
        drugs = list(top_drugs_prescribed(start, end))
        turnaround = list(lab_turnaround(start, end))
        volume = list(encounter_volume(start, end))

        diag_labels = json.dumps([d["icd10_code"] for d in diagnoses])
        diag_data = json.dumps([d["count"] for d in diagnoses])
        vol_labels = json.dumps([str(v["day"]) for v in volume])
        vol_data = json.dumps([v["count"] for v in volume])

        return render(request, self.template_name, {
            "start": start,
            "end": end,
            "diagnoses": diagnoses,
            "drugs": drugs,
            "turnaround": turnaround,
            "diag_labels": diag_labels,
            "diag_data": diag_data,
            "vol_labels": vol_labels,
            "vol_data": vol_data,
        })


@method_decorator(login_required, name="dispatch")
class MonthlyReturnView(View):
    template_name = "reports/monthly_return.html"

    def get(self, request):
        today = timezone.localdate()
        try:
            year = int(request.GET.get("year", today.year))
            month = int(request.GET.get("month", today.month))
        except ValueError:
            year, month = today.year, today.month

        from reports.services import monthly_return
        data = monthly_return(year, month)
        months = [(y, m) for y in range(2024, today.year + 1)
                  for m in range(1, 13)
                  if date(y, m, 1) <= today]
        return render(request, self.template_name, {
            "data": data, "year": year, "month": month, "months": months,
            "year_range": list(range(2024, today.year + 2)),
            "month_range": list(range(1, 13)),
        })


@method_decorator(login_required, name="dispatch")
class ClaimsListView(View):
    template_name = "reports/claims.html"

    def get(self, request):
        from integrations.models import ClaimBatch, Payer
        payers = Payer.objects.filter(is_active=True)
        payer_pk = request.GET.get("payer")
        batches = ClaimBatch.objects.none()
        payer = None
        if payer_pk:
            from django.shortcuts import get_object_or_404
            payer = get_object_or_404(Payer, pk=payer_pk)
            batches = ClaimBatch.objects.filter(
                payer=payer
            ).prefetch_related("claims").order_by("-period_start")
        return render(request, self.template_name, {
            "payers": payers,
            "payer": payer,
            "batches": batches,
        })


@method_decorator(login_required, name="dispatch")
class ClaimBatchCreateView(View):
    template_name = "reports/claim_batch_create.html"

    def get(self, request):
        from integrations.models import Payer
        payers = Payer.objects.filter(is_active=True)
        today = timezone.localdate()
        return render(request, self.template_name, {
            "payers": payers,
            "default_start": date(today.year, today.month, 1),
            "default_end": today,
        })

    def post(self, request):
        from django.contrib import messages
        from integrations.models import Payer
        from integrations.services import build_claim_batch
        payer_pk = request.POST.get("payer")
        try:
            start = date.fromisoformat(request.POST.get("period_start", ""))
            end = date.fromisoformat(request.POST.get("period_end", ""))
        except ValueError:
            messages.error(request, "Invalid date range.")
            return self.get(request)

        from django.shortcuts import get_object_or_404
        payer = get_object_or_404(Payer, pk=payer_pk)
        batch, claims = build_claim_batch(payer, start, end, submitted_by=request.user)
        messages.success(
            request,
            f"Claim batch created: {len(claims)} claims totalling ₦{batch.total_claimed}.",
        )
        from django.shortcuts import redirect
        return redirect("reports:claims")


@method_decorator(login_required, name="dispatch")
class ClaimBatchSubmitView(View):
    def post(self, request, pk):
        from django.contrib import messages
        from django.shortcuts import get_object_or_404, redirect
        from integrations.models import ClaimBatch
        from integrations.services import submit_batch
        batch = get_object_or_404(ClaimBatch, pk=pk)
        try:
            submit_batch(batch, request.user)
            messages.success(request, f"Batch {batch} submitted.")
        except ValueError as e:
            messages.error(request, str(e))
        return redirect("reports:claims")
