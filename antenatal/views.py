from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils.decorators import method_decorator
from django.views import View

from .models import ANCRecord


@method_decorator(login_required, name="dispatch")
class ANCListView(View):
    template_name = "antenatal/list.html"

    def get(self, request):
        today = date.today()
        qs = (
            ANCRecord.objects.filter(is_active=True)
            .select_related("patient")
            .prefetch_related("visits")
            .order_by("edd")
        )

        q = request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                patient__first_name__icontains=q
            ) | qs.filter(
                patient__last_name__icontains=q
            ) | qs.filter(
                patient__hospital_number__icontains=q
            )

        filter_val = request.GET.get("filter", "all")
        if filter_val == "due_soon":
            qs = qs.filter(edd__lte=today + timedelta(weeks=4))
        elif filter_val == "early":
            qs = qs.filter(edd__gte=today + timedelta(weeks=28))

        return render(request, self.template_name, {
            "records": qs,
            "today": today,
            "q": q,
            "filter_val": filter_val,
            "total_active": ANCRecord.objects.filter(is_active=True).count(),
            "due_soon_count": ANCRecord.objects.filter(
                is_active=True, edd__lte=today + timedelta(weeks=4)
            ).count(),
        })


@method_decorator(login_required, name="dispatch")
class ANCDetailView(View):
    template_name = "antenatal/detail.html"

    def get(self, request, pk):
        record = get_object_or_404(
            ANCRecord.objects.select_related("patient")
            .prefetch_related("visits", "scans"),
            pk=pk,
        )
        return render(request, self.template_name, {
            "record": record,
            "patient": record.patient,
            "today": date.today(),
        })
