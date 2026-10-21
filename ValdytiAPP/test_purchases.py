from datetime import date
from decimal import Decimal
import json
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.urls import reverse

from .forms import PurchaseForm
from .models import Purchase


class PurchaseTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("purchase-admin", password="test-password")
        self.client.force_login(self.admin)

    def purchase(self, **overrides):
        data = dict(purchase_date=date(2026, 10, 21), store="lidl", category="meat",
                    name="Kiaulienos mentė", quantity=Decimal("2.000"), unit="kg",
                    unit_price=Decimal("5.0000"), total=Decimal("10.00"))
        data.update(overrides)
        return Purchase.objects.create(**data)

    def report(self, **params):
        return self.client.get(reverse("purchase-list"), params)

    def test_daily_report_groups_products_and_uses_paid_total_for_average(self):
        self.purchase()
        self.purchase(name="kiaulienos mentė", store="norfa", quantity=Decimal("3.000"),
                      unit_price=Decimal("6.0000"), total=Decimal("15.00"))
        self.purchase(category="vegetables", name="Bulvės", total=Decimal("4.20"))
        self.purchase(purchase_date=date(2026, 10, 20), total=Decimal("99.00"))
        response = self.report(date="2026-10-21")
        self.assertEqual(response.status_code, 200)
        meat = response.context["purchase_groups"][0]
        self.assertEqual(len(meat["products"]), 1)
        product = meat["products"][0]
        self.assertEqual(product["quantity"], Decimal("5"))
        self.assertEqual(product["average_price"], Decimal("5"))
        self.assertEqual(len(product["entries"]), 2)
        self.assertEqual(response.context["grand_total"], Decimal("29.20"))
        self.assertEqual([s["total"] for s in response.context["store_totals"]],
                         [Decimal("14.20"), Decimal("15"), Decimal("0"), Decimal("0"), Decimal("0")])
        self.assertContains(response, "Prekių pirkimas")
        self.assertContains(response, reverse("purchase-update", args=[product["entries"][0].pk]))

    def test_different_units_and_categories_are_not_combined(self):
        self.purchase()
        self.purchase(unit="vnt")
        self.purchase(category="other")
        response = self.report(date="2026-10-21")
        self.assertEqual(len(response.context["purchase_groups"][0]["products"]), 2)
        self.assertEqual(len(response.context["purchase_groups"][2]["products"]), 1)

    def test_week_is_monday_through_sunday_across_year_boundary(self):
        for day in (date(2025, 12, 28), date(2025, 12, 29), date(2026, 1, 4), date(2026, 1, 5)):
            self.purchase(purchase_date=day)
        response = self.report(date="2026-01-01", period="week")
        self.assertEqual(response.context["date_from"], date(2025, 12, 29))
        self.assertEqual(response.context["date_to"], date(2026, 1, 4))
        self.assertEqual(response.context["grand_total"], Decimal("20"))
        self.assertEqual(len(response.context["daily_totals"]), 2)

    def test_month_boundaries_include_leap_day(self):
        for day in (date(2024, 1, 31), date(2024, 2, 1), date(2024, 2, 29), date(2024, 3, 1)):
            self.purchase(purchase_date=day)
        response = self.report(date="2024-02-10", period="month")
        self.assertEqual(response.context["date_to"], date(2024, 2, 29))
        self.assertEqual(response.context["grand_total"], Decimal("20"))
        self.assertEqual(sum(r["total"] for r in response.context["daily_totals"]), Decimal("20"))

    def test_default_date_is_latest_and_dates_are_unique(self):
        self.purchase()
        self.purchase()
        self.purchase(purchase_date=date(2026, 10, 19))
        response = self.report()
        self.assertEqual(response.context["selected_date"], date(2026, 10, 21))
        self.assertEqual(response.context["available_dates"], [date(2026, 10, 21), date(2026, 10, 19)])
        self.assertEqual(self.report(date="invalid", period="invalid").status_code, 200)

    def test_empty_day_shows_all_stores_and_zero_total(self):
        response = self.report(date="2026-10-21")
        self.assertEqual(response.context["grand_total"], Decimal("0"))
        self.assertEqual(len(response.context["store_totals"]), 5)

    def test_unknown_quantity_and_payment_adjustment_do_not_distort_product_cost(self):
        self.purchase(name="Svogūnų laiškai", quantity=None, unit="", unit_price=None,
                      store="other", category="vegetables", total=Decimal("6.65"))
        self.purchase(payment_adjustment=Decimal("-0.12"))
        response = self.report(date="2026-10-21")
        product = response.context["purchase_groups"][1]["products"][0]
        self.assertIsNone(product["quantity"])
        self.assertIsNone(product["average_price"])
        self.assertEqual(response.context["goods_total"], Decimal("16.65"))
        self.assertEqual(response.context["grand_total"], Decimal("16.53"))
        self.assertContains(response, "Kiekis nenurodytas")

    def test_receipt_import_checks_totals_and_is_repeatable_without_duplicates(self):
        receipt = {
            "date": "2026-10-21", "store": "lidl", "reference": "TEST-RECEIPT",
            "goods_total": "10.00", "paid_total": "9.99", "payment_adjustment": "-0.01",
            "items": [{"name": "Mėsa", "category": "meat", "quantity": "2.000",
                       "unit": "kg", "unit_price": "5.00", "total": "10.00"}],
        }
        def run(data, **options):
            with patch("ValdytiAPP.management.commands.import_purchase_receipts.Path.read_text",
                       return_value=json.dumps({"receipts": [data]})):
                call_command("import_purchase_receipts", "unused.json", stdout=StringIO(), **options)
        run(receipt, dry_run=True)
        self.assertEqual(Purchase.objects.count(), 0)
        run(receipt)
        run(receipt)
        self.assertEqual(Purchase.objects.count(), 1)
        with self.assertRaises(CommandError):
            run({**receipt, "paid_total": "999.00"})
        self.assertEqual(Purchase.objects.count(), 1)
        changed = {**receipt, "items": [{**receipt["items"][0], "name": "Pakeista"}]}
        with self.assertRaises(CommandError):
            run(changed)
        self.assertEqual(Purchase.objects.get().name, "Mėsa")

    def test_create_edit_delete_and_add_another(self):
        data = dict(purchase_date="2026-10-21", store="iki", category="meat",
                    name="  Kiaulienos   mentė  ", quantity="1.250", unit="kg",
                    unit_price="4.0000", total="4.50", receipt_reference="TEST-1", notes="Nuolaida")
        response = self.client.post(reverse("purchase-create"), data)
        item = Purchase.objects.get()
        self.assertRedirects(response, reverse("purchase-list") + "?date=2026-10-21")
        self.assertEqual(item.name, "Kiaulienos mentė")
        self.assertEqual(item.total, Decimal("4.50"))
        data.update(total="4.00", purchase_date="2026-10-22")
        self.client.post(reverse("purchase-update", args=[item.pk]), data)
        item.refresh_from_db()
        self.assertEqual(item.total, Decimal("4.00"))
        self.assertEqual(item.purchase_date, date(2026, 10, 22))
        self.assertEqual(self.client.get(reverse("purchase-delete", args=[item.pk])).status_code, 200)
        self.assertTrue(Purchase.objects.filter(pk=item.pk).exists())
        self.client.post(reverse("purchase-delete", args=[item.pk]))
        self.assertFalse(Purchase.objects.exists())
        response = self.client.post(reverse("purchase-create"), {**data, "add_another": "1"})
        self.assertRedirects(response, reverse("purchase-create") + "?date=2026-10-22")

    def test_invalid_quantity_amount_and_unknown_store_rejected(self):
        data = dict(purchase_date="2026-10-21", store="lidl", category="meat", name="Mėsa",
                    quantity="1", unit="kg", unit_price="4", total="4")
        for invalid in ({"quantity": "0"}, {"unit_price": "-1"}, {"total": "-1"},
                        {"store": "unknown"}, {"name": "   "}):
            self.assertFalse(PurchaseForm({**data, **invalid}).is_valid())

    def test_permissions_protect_all_routes(self):
        item = self.purchase()
        urls = [reverse("purchase-list"), reverse("purchase-create"),
                reverse("purchase-update", args=[item.pk]), reverse("purchase-delete", args=[item.pk])]
        self.client.logout()
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)
        user = get_user_model().objects.create_user("purchase-viewer", password="test-password")
        self.client.force_login(user)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
        user.user_permissions.add(Permission.objects.get(codename="view_purchase", content_type__app_label="valdyti"))
        self.assertEqual(self.client.get(urls[0]).status_code, 200)
        self.assertEqual(self.client.post(urls[3]).status_code, 403)
