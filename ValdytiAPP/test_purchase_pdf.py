from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from pypdf import PdfReader

from .models import Purchase


class PurchasePdfTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("pdf-viewer", password="test-password")
        self.user.user_permissions.add(Permission.objects.get(
            content_type__app_label="valdyti", codename="view_purchase"))
        self.client.force_login(self.user)

    def purchase(self, **overrides):
        data = dict(purchase_date=date(2026, 10, 21), store="lidl", category="meat",
                    name="Kiaulienos mentė", quantity=Decimal("2"), unit="kg",
                    unit_price=Decimal("5"), total=Decimal("10"))
        data.update(overrides)
        return Purchase.objects.create(**data)

    def pdf(self, **params):
        response = self.client.get(reverse("purchase-daily-pdf"), params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        data = b"".join(response.streaming_content)
        response.close()
        self.assertTrue(data.startswith(b"%PDF-"))
        return PdfReader(BytesIO(data)), response

    def test_selected_day_only_even_when_week_period_is_supplied(self):
        self.purchase(payment_adjustment=Decimal("-0.01"))
        self.purchase(purchase_date=date(2026, 10, 20), name="NEĮTRAUKTI", total=Decimal("100"))
        reader, response = self.pdf(date="2026-10-21", period="week")
        text = "\n".join(page.extract_text() for page in reader.pages)
        self.assertEqual(len(reader.pages), 1)
        self.assertIn("prekiu-pirkimas-2026-10-21.pdf", response["Content-Disposition"])
        self.assertIn("Kiaulienos mentė", text)
        self.assertIn("9,99 €", text)
        self.assertNotIn("NEĮTRAUKTI", text)
        self.assertAlmostEqual(float(reader.pages[0].mediabox.width), 595.2756, places=2)
        self.assertAlmostEqual(float(reader.pages[0].mediabox.height), 841.8898, places=2)
        fonts = reader.pages[0]["/Resources"]["/Font"].get_object().values()
        self.assertTrue(any("/FontFile2" in font.get_object().get("/FontDescriptor", {})
                            for font in fonts))

    def test_daily_sized_report_fits_one_a4_with_unknown_quantity_and_escaped_names(self):
        for index in range(17):
            self.purchase(name=f"Daržovės <šviežios> & prekė {index}",
                          category=("meat", "vegetables", "other")[index % 3])
        self.purchase(name="Svogūnų laiškai", category="vegetables", store="other",
                      quantity=None, unit="", unit_price=None, total=Decimal("6.65"))
        reader, _ = self.pdf(date="2026-10-21")
        self.assertEqual(len(reader.pages), 1)
        text = reader.pages[0].extract_text()
        self.assertIn("Daržovės <šviežios> & prekė 0", text)
        self.assertIn("Svogūnų laiškai", text)
        self.assertIn("176,65 €", text)

    def test_empty_day_can_be_printed(self):
        reader, _ = self.pdf(date="2026-10-21")
        self.assertEqual(len(reader.pages), 1)
        self.assertIn("Pirkimų nėra.", reader.pages[0].extract_text())

    def test_long_report_paginates_and_keeps_all_products(self):
        for index in range(85):
            self.purchase(name=f"Prekė {index:03d} - ilgas lietuviškas pavadinimas su ąčęėįšųūž")
        reader, _ = self.pdf(date="2026-10-21")
        self.assertGreater(len(reader.pages), 1)
        text = "\n".join(page.extract_text() for page in reader.pages)
        for index in range(85):
            self.assertIn(f"Prekė {index:03d}", text)
        self.assertIn("850,00 €", text)
        for page in reader.pages:
            self.assertIn("Lapas", page.extract_text())

    def test_export_requires_login_and_view_permission(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("purchase-daily-pdf")).status_code, 302)
        other = get_user_model().objects.create_user("pdf-no-permission", password="test-password")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("purchase-daily-pdf")).status_code, 403)
