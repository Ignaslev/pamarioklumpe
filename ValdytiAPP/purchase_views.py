"""Manual receipt-line entry and calendar-based purchasing reports."""

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import FileResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, TemplateView, UpdateView

from .forms import PurchaseForm
from .models import Purchase, PurchaseReceipt


def selected_date(value, fallback):
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return fallback


def purchase_url(day):
    return f"{reverse('purchase-list')}?date={day.isoformat()}"


class PurchaseListView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = "valdyti.view_purchase"
    template_name = "ValdytiAPP/pirkimai/purchase_list.html"
    report_period = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        available_dates = list(Purchase.objects.order_by("-purchase_date")
                               .values_list("purchase_date", flat=True).distinct())
        day = selected_date(self.request.GET.get("date"),
                            available_dates[0] if available_dates else timezone.localdate())
        period = self.report_period or self.request.GET.get("period", "day")
        if period not in {"day", "week", "month"}:
            period = "day"
        start = end = day
        if period == "week":
            start = day - timedelta(days=day.weekday())
            end = start + timedelta(days=6)
        elif period == "month":
            start = day.replace(day=1)
            end = day.replace(day=monthrange(day.year, day.month)[1])

        purchases = list(Purchase.objects.filter(purchase_date__range=(start, end)).select_related("receipt")
                         .order_by("purchase_date", "name", "pk"))
        store_totals = {key: {"name": label, "total": Decimal("0.00"), "count": 0}
                        for key, label in Purchase.Store.choices}
        groups = {key: {"name": label, "products": {}, "total": Decimal("0.00")}
                  for key, label in Purchase.Category.choices}
        daily = {}
        grand_total = Decimal("0.00")
        goods_total = Decimal("0.00")
        payment_adjustments = Decimal("0.00")
        for item in purchases:
            paid = item.total + item.payment_adjustment
            goods_total += item.total
            payment_adjustments += item.payment_adjustment
            grand_total += paid
            store_totals[item.store]["total"] += paid
            store_totals[item.store]["count"] += 1
            group = groups[item.category]
            group["total"] += item.total
            # Never combine kilograms with pieces or litres.
            key = (" ".join(item.name.split()).casefold(), item.unit)
            product = group["products"].setdefault(key, {
                "name": item.name, "unit": item.get_unit_display(),
                "quantity": Decimal("0"), "quantity_unknown": False,
                "total": Decimal("0.00"), "entries": [],
            })
            if item.quantity is None:
                product["quantity_unknown"] = True
            else:
                product["quantity"] += item.quantity
            product["total"] += item.total
            product["entries"].append(item)
            daily.setdefault(item.purchase_date, {
                "date": item.purchase_date, "total": Decimal("0.00"),
                "stores": {key: Decimal("0.00") for key, _ in Purchase.Store.choices},
            })
            daily[item.purchase_date]["total"] += paid
            daily[item.purchase_date]["stores"][item.store] += paid

        for group in groups.values():
            group["products"] = sorted(group["products"].values(), key=lambda p: p["name"].casefold())
            for product in group["products"]:
                if product["quantity_unknown"]:
                    product["quantity"] = None
                    product["average_price"] = None
                else:
                    product["average_price"] = product["total"] / product["quantity"]
        for row in daily.values():
            row["store_values"] = list(row["stores"].values())
        context.update({
            "selected_date": day, "available_dates": available_dates, "period": period,
            "date_from": start, "date_to": end, "purchase_groups": list(groups.values()),
            "store_totals": list(store_totals.values()), "grand_total": grand_total,
            "goods_total": goods_total, "payment_adjustments": payment_adjustments,
            "purchase_count": len(purchases), "daily_totals": sorted(daily.values(), key=lambda r: r["date"]),
            "receipts": PurchaseReceipt.objects.filter(purchase_date__range=(start, end)),
        })
        return context


class PurchaseDailyPdfView(PurchaseListView):
    report_period = "day"

    def get(self, request, *args, **kwargs):
        from .purchase_pdf import build_daily_purchase_pdf

        context = self.get_context_data(**kwargs)
        filename = f"prekiu-pirkimas-{context['selected_date'].isoformat()}.pdf"
        response = FileResponse(build_daily_purchase_pdf(context), as_attachment=True,
                                filename=filename, content_type="application/pdf")
        response["Cache-Control"] = "private, no-store"
        return response


class PurchaseCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Purchase
    form_class = PurchaseForm
    permission_required = "valdyti.add_purchase"
    template_name = "ValdytiAPP/pirkimai/purchase_form.html"

    def get_initial(self):
        initial = super().get_initial()
        initial["purchase_date"] = selected_date(self.request.GET.get("date"), timezone.localdate())
        return initial

    def get_success_url(self):
        if self.request.POST.get("add_another"):
            return f"{reverse('purchase-create')}?date={self.object.purchase_date.isoformat()}"
        return purchase_url(self.object.purchase_date)

    def form_valid(self, form):
        messages.success(self.request, "Pirkimas įrašytas.")
        return super().form_valid(form)


class PurchaseUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Purchase
    form_class = PurchaseForm
    permission_required = "valdyti.change_purchase"
    template_name = "ValdytiAPP/pirkimai/purchase_form.html"

    def get(self, request, *args, **kwargs):
        if self.get_object().receipt_id:
            return redirect("receipt-review", pk=self.get_object().receipt_id)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.get_object().receipt_id:
            return redirect("receipt-review", pk=self.get_object().receipt_id)
        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        return purchase_url(self.object.purchase_date)

    def form_valid(self, form):
        messages.success(self.request, "Pirkimas atnaujintas.")
        return super().form_valid(form)


class PurchaseDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Purchase
    permission_required = "valdyti.delete_purchase"
    template_name = "ValdytiAPP/pirkimai/purchase_confirm_delete.html"

    def get(self, request, *args, **kwargs):
        if self.get_object().receipt_id:
            return redirect("receipt-review", pk=self.get_object().receipt_id)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self.get_object().receipt_id:
            return redirect("receipt-review", pk=self.get_object().receipt_id)
        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        return purchase_url(self.object.purchase_date)
