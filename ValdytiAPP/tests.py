import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from .models import Invoice, MenuCategory, MenuItem, Worker


class WorkerManagementTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin", email="admin@example.com", password="test-password-123"
        )
        self.worker = Worker.objects.create(
            first_name="Jonas", last_name="Jonaitis", job_title="Virėjas"
        )

    def test_worker_list_requires_login(self):
        response = self.client.get(reverse("worker-list"))
        self.assertEqual(response.status_code, 302)

    def test_admin_can_create_worker(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("worker-create"),
            {
                "first_name": "Ona",
                "last_name": "Onaitė",
                "job_title": "Padavėja",
                "phone": "",
                "email": "",
                "notes": "",
            },
        )
        self.assertRedirects(response, reverse("worker-list"))
        self.assertTrue(Worker.objects.filter(first_name="Ona").exists())

    def test_admin_can_delete_worker(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("worker-delete", args=[self.worker.pk]))
        self.assertRedirects(response, reverse("worker-list"))
        self.assertFalse(Worker.objects.filter(pk=self.worker.pk).exists())

    def test_menu_requires_login(self):
        response = self.client.get(reverse("menu-list"))
        self.assertEqual(response.status_code, 302)

    def test_admin_can_create_menu_item(self):
        category, _ = MenuCategory.objects.get_or_create(name="Sriubos")
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("menu-item-create"),
            {
                "category": category.pk,
                "name": "Dienos sriuba",
                "description": "",
                "price": "1.50",
                "second_price": "2.00",
                "sort_order": 1,
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("menu-list"))
        self.assertTrue(MenuItem.objects.filter(name="Dienos sriuba").exists())

    def test_category_with_menu_items_cannot_be_deleted(self):
        category, _ = MenuCategory.objects.get_or_create(name="Sriubos")
        MenuItem.objects.create(category=category, name="Dienos sriuba", price="1.50")
        self.client.force_login(self.admin)
        response = self.client.post(reverse("menu-category-delete", args=[category.pk]))
        self.assertRedirects(response, reverse("menu-category-list"))
        self.assertTrue(MenuCategory.objects.filter(pk=category.pk).exists())


class InvoiceManagementTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="invoice-admin", email="invoice-admin@example.com", password="test-password-123"
        )
        self.temp_media = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media.name)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        self.temp_media.cleanup()

    def sample_pdf(self):
        return SimpleUploadedFile(
            "saskaita.pdf",
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n",
            content_type="application/pdf",
        )

    def extraction(self):
        return {
            "invoice": {
                "invoice_number": "INV-42", "invoice_date": "2026-07-28", "due_date": None,
                "supplier_name": "Tiekejas", "supplier_company_code": None, "supplier_vat_id": "LT123",
                "supplier_address": None, "buyer_name": "Pamario Klumpe", "buyer_company_code": None,
                "buyer_vat_id": None, "buyer_address": None, "subtotal": 10.0, "vat_rate": 21.0,
                "vat_amount": 2.1, "total": 12.1, "currency": "EUR",
            },
            "lines": [{"line_number": 1, "product_code": "A1", "name": "Produktas", "unit": "vnt.", "quantity": 2.0, "unit_price": 5.0, "total": 10.0}],
        }

    def test_invoice_list_requires_login(self):
        response = self.client.get(reverse("invoice-list"))
        self.assertEqual(response.status_code, 302)

    @patch("ValdytiAPP.views.parse_invoice_pdf")
    def test_upload_saves_pdf_and_rejects_same_file(self, parse_invoice_pdf):
        parse_invoice_pdf.return_value = (self.extraction(), "test-model")
        self.client.force_login(self.admin)
        response = self.client.post(reverse("invoice-upload"), {"pdf": self.sample_pdf()})
        invoice = Invoice.objects.get()
        self.assertRedirects(response, reverse("invoice-update", args=[invoice.pk]))
        self.assertTrue(invoice.source_file.storage.exists(invoice.source_file.name))
        self.assertEqual(invoice.lines.count(), 1)

        duplicate_response = self.client.post(reverse("invoice-upload"), {"pdf": self.sample_pdf()})
        self.assertRedirects(duplicate_response, reverse("invoice-list"))
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(parse_invoice_pdf.call_count, 1)

    @patch("ValdytiAPP.views.parse_invoice_pdf")
    def test_saved_pdf_can_be_downloaded(self, parse_invoice_pdf):
        parse_invoice_pdf.return_value = (self.extraction(), "test-model")
        self.client.force_login(self.admin)
        self.client.post(reverse("invoice-upload"), {"pdf": self.sample_pdf()})
        invoice = Invoice.objects.get()
        response = self.client.get(reverse("invoice-pdf", args=[invoice.pk]) + "?download=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        response.close()
