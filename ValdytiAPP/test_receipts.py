import json
import os
import shutil
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from PIL import Image
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Purchase, PurchaseReceipt
from .receipt_parser import ReceiptParserError, amount, image_inputs, normalized_receipt, parse_receipt_image


def sample_receipt(**overrides):
    raw = {
        "purchase_date": "2026-10-21", "store": "lidl", "store_name": "Lidl Lietuva",
        "store_address": "Šilutė", "receipt_number": "CR-12345", "goods_total": "10.00",
        "paid_total": "9.99", "receipt_discount": "0", "payment_adjustment": "-0.01",
        "needs_review": False, "warnings": [],
        "items": [{"name": "Kiaulienos mentė", "category": "meat", "quantity": "2.000",
                   "unit": "kg", "unit_price": "5.0000", "gross_total": "10.00",
                   "line_discount": "0", "notes": ""}],
    }
    raw.update(overrides)
    return raw


def photo(color="white", name="čekis.jpg"):
    buffer = BytesIO()
    Image.new("RGB", (40, 60), color).save(buffer, "JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


class ReceiptParserTests(SimpleTestCase):
    def test_arithmetic_and_printed_date(self):
        meta, rows, issues = normalized_receipt(sample_receipt())
        self.assertEqual(meta["purchase_date"], date(2026, 10, 21))
        self.assertEqual(rows[0]["quantity"], Decimal("2.000"))
        self.assertEqual(rows[0]["total"], Decimal("10.00"))
        self.assertEqual(meta["payment_adjustment"], Decimal("-0.01"))
        self.assertEqual(issues, [])

    def test_line_and_receipt_discounts_are_applied_once_exactly(self):
        raw = sample_receipt(goods_total="8.99", paid_total="8.99", payment_adjustment="0", receipt_discount="0.01")
        item = raw["items"][0]
        item.update(gross_total="5", line_discount="1", quantity="1")
        raw["items"].append({**item, "name": "Kumpis", "gross_total": "5", "line_discount": "0"})
        _, rows, issues = normalized_receipt(raw)
        self.assertEqual([x["total"] for x in rows], [Decimal("4.00"), Decimal("4.99")])
        self.assertEqual(issues, [])

    def test_loyalty_payment_is_not_deducted_from_product_cost(self):
        raw = sample_receipt(store="norfa", goods_total="10", paid_total="9.88", payment_adjustment="-0.12")
        meta, rows, issues = normalized_receipt(raw)
        self.assertEqual(rows[0]["total"], Decimal("10"))
        self.assertEqual(meta["paid_total"], Decimal("9.88"))
        self.assertEqual(issues, [])

    def test_unknown_quantity_not_invented_and_mismatch_requires_review(self):
        raw = sample_receipt(goods_total="11")
        raw["items"][0].update(quantity=None, unit="", unit_price=None)
        _, rows, issues = normalized_receipt(raw)
        self.assertIsNone(rows[0]["quantity"])
        self.assertIsNone(rows[0]["unit_price"])
        self.assertTrue(issues)

    def test_missing_date_number_generic_name_requires_review(self):
        raw = sample_receipt(purchase_date=None, receipt_number=None)
        raw["items"][0]["name"] = "Prekė (nepatikslinta)"
        meta, _, issues = normalized_receipt(raw)
        self.assertIsNone(meta["purchase_date"])
        self.assertGreaterEqual(len(issues), 3)

    def test_non_finite_and_extreme_amounts_rejected(self):
        for value in ("NaN", "Infinity", "1e200", "abc"):
            self.assertIsNone(amount(value))
        self.assertEqual(amount("1,23"), Decimal("1.23"))

    def test_misread_year_and_product_arithmetic_require_review(self):
        raw = sample_receipt(purchase_date="2023-10-21", receipt_number="123-20261021")
        raw["items"][0]["quantity"] = "3"
        _, _, issues = normalized_receipt(raw)
        self.assertTrue(any("numerio data" in issue for issue in issues))
        self.assertTrue(any("kiekis ×" in issue for issue in issues))

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-real", "OPENAI_RECEIPT_MODEL": "gpt-6.1-sol", "OPENAI_RECEIPT_REASONING": "medium"})
    @patch("openai.OpenAI")
    def test_sol_uses_requested_model_reasoning_and_original_image(self, api):
        api.return_value.__enter__.return_value.responses.create.return_value = SimpleNamespace(
            status="completed", output_text=json.dumps(sample_receipt()))
        _, model = parse_receipt_image(photo().read())
        kwargs = api.return_value.__enter__.return_value.responses.create.call_args.kwargs
        self.assertEqual(model, "gpt-6.1-sol")
        self.assertEqual(kwargs["reasoning"], {"effort": "medium"})
        self.assertEqual(kwargs["input"][0]["content"][1]["detail"], "original")

    @patch.dict(os.environ, {"OPENAI_API_KEY": ""})
    def test_missing_key_friendly_error(self):
        with self.assertRaisesMessage(ReceiptParserError, "OPENAI_API_KEY"):
            parse_receipt_image(photo().read())

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-real", "OPENAI_RECEIPT_MODEL": "gpt-4o"})
    @patch("openai.OpenAI")
    def test_structured_image_request_does_not_store_api_response(self, api):
        api.return_value.__enter__.return_value.responses.create.return_value = SimpleNamespace(
            status="completed", output_text=json.dumps(sample_receipt()))
        raw, model = parse_receipt_image(photo().read())
        call = api.return_value.__enter__.return_value.responses.create.call_args.kwargs
        self.assertEqual(raw["receipt_number"], "CR-12345")
        self.assertEqual(model, "gpt-4o")
        self.assertFalse(call["store"])
        self.assertTrue(call["text"]["format"]["strict"])
        self.assertEqual(call["input"][0]["content"][1]["type"], "input_image")

    def test_image_validation_and_encoding(self):
        self.assertEqual(len(image_inputs(photo().read())), 1)
        with self.assertRaises(ReceiptParserError):
            image_inputs(b"<script>not an image</script>")


class ReceiptWorkflowTests(TestCase):
    def setUp(self):
        test_root = settings.BASE_DIR / "tmp" / "receipt-tests"
        test_root.mkdir(parents=True, exist_ok=True)
        self.temp = test_root / uuid4().hex
        self.temp.mkdir()
        self.addCleanup(shutil.rmtree, self.temp)
        self.storage_settings = override_settings(RECEIPT_STORAGE_ROOT=self.temp)
        self.storage_settings.enable()
        self.addCleanup(self.storage_settings.disable)
        self.user = get_user_model().objects.create_superuser("receipt-admin", password="test-password")
        self.client.force_login(self.user)

    def upload(self, color="white"):
        response = self.client.post(reverse("receipt-upload"), {"image": photo(color)})
        self.assertIn(response.status_code, (200, 201), response.content)
        return PurchaseReceipt.objects.get(pk=response.json()["id"])

    def process(self, receipt, raw=None):
        with patch("ValdytiAPP.receipt_views.parse_receipt_image", return_value=(raw or sample_receipt(), "test-model")) as parser:
            response = self.client.post(reverse("receipt-process", args=[receipt.pk]))
        receipt.refresh_from_db()
        return response, parser

    def review_data(self, **overrides):
        data = dict(purchase_date="2026-10-21", store="lidl", store_name="Lidl", store_address="Šilutė",
                    receipt_number="CR-12345", goods_total="10.00", paid_total="9.99", payment_adjustment="-0.01",
                    **{"lines-TOTAL_FORMS": "1", "lines-INITIAL_FORMS": "0", "lines-MIN_NUM_FORMS": "0",
                       "lines-MAX_NUM_FORMS": "500", "lines-0-name": "Kiaulienos mentė", "lines-0-category": "meat",
                       "lines-0-quantity": "2.000", "lines-0-unit": "kg", "lines-0-unit_price": "5.0000",
                       "lines-0-total": "10.00", "lines-0-notes": "Patikrinta"})
        data.update(overrides)
        return data

    def test_upload_saves_private_original_and_same_file_is_idempotent(self):
        receipt = self.upload()
        second = self.upload()
        self.assertEqual(receipt.pk, second.pk)
        self.assertTrue(Path(receipt.source_file.path).is_relative_to(self.temp))
        self.assertEqual(Path(receipt.source_file.path).read_bytes(), photo().read())
        with self.assertRaises(ValueError):
            _ = receipt.source_file.url
        self.assertFalse(Purchase.objects.exists())

    def test_invalid_image_and_size_rejected_without_db_writes(self):
        response = self.client.post(reverse("receipt-upload"), {"image": SimpleUploadedFile("x.jpg", b"not image")})
        self.assertEqual(response.status_code, 400)
        with override_settings(RECEIPT_UPLOAD_MAX_BYTES=10):
            response = self.client.post(reverse("receipt-upload"), {"image": photo()})
            self.assertEqual(response.status_code, 400)
        self.assertFalse(PurchaseReceipt.objects.exists())

    def test_success_adds_all_lines_and_repeated_process_uses_no_api(self):
        receipt = self.upload()
        response, parser = self.process(receipt)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(receipt.status, "ready")
        item = receipt.purchases.get()
        self.assertEqual(item.total, Decimal("10.00"))
        self.assertEqual(item.payment_adjustment, Decimal("-0.01"))
        response, parser = self.process(receipt)
        parser.assert_not_called()
        self.assertEqual(receipt.purchases.count(), 1)
        report = self.client.get(reverse("purchase-list"), {"date": "2026-10-21"})
        self.assertEqual(report.context["grand_total"], Decimal("9.99"))
        self.assertContains(report, reverse("receipt-review", args=[receipt.pk]))

    def test_different_photo_same_number_is_duplicate_without_extra_purchases(self):
        first, second = self.upload(), self.upload("red")
        self.process(first)
        self.process(second)
        self.assertEqual(second.status, "duplicate")
        self.assertEqual(second.duplicate_of, first)
        self.assertEqual(Purchase.objects.count(), 1)

    def test_existing_manual_receipt_is_not_imported_again(self):
        Purchase.objects.create(purchase_date=date(2026, 10, 21), store="lidl", category="meat", name="Mentė",
                                total="10", receipt_reference="CR-12345")
        receipt = self.upload()
        self.process(receipt)
        self.assertEqual(receipt.status, "duplicate")
        self.assertEqual(Purchase.objects.count(), 1)

    def test_mismatch_is_review_only_not_silently_balanced(self):
        receipt = self.upload()
        self.process(receipt, sample_receipt(goods_total="11", paid_total="10.99"))
        self.assertEqual(receipt.status, "review")
        self.assertTrue(receipt.warnings)
        self.assertFalse(receipt.purchases.exists())
        _, parser = self.process(receipt)
        parser.assert_not_called()

    def test_ai_failure_keeps_original_and_retry_succeeds(self):
        receipt = self.upload()
        with patch("ValdytiAPP.receipt_views.parse_receipt_image", side_effect=ReceiptParserError("Paslauga nepasiekiama")):
            response = self.client.post(reverse("receipt-process", args=[receipt.pk]))
        self.assertEqual(response.status_code, 422)
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, "failed")
        self.assertTrue(Path(receipt.source_file.path).exists())
        self.process(receipt)
        self.assertEqual(receipt.status, "ready")
        self.assertEqual(receipt.processing_attempt, 2)

    def test_recent_processing_is_locked_stale_processing_can_retry(self):
        receipt = self.upload()
        receipt.status, receipt.processing_started_at = "processing", timezone.now()
        receipt.save()
        response, parser = self.process(receipt)
        self.assertEqual(response.status_code, 409)
        parser.assert_not_called()
        receipt.processing_started_at = timezone.now() - timedelta(minutes=6)
        receipt.save()
        self.process(receipt)
        self.assertEqual(receipt.status, "ready")

    def test_review_corrects_draft_and_saving_twice_replaces_not_appends(self):
        receipt = self.upload()
        self.process(receipt, sample_receipt(needs_review=True))
        page = self.client.get(reverse("receipt-review", args=[receipt.pk]))
        self.assertEqual(page.status_code, 200)
        for _ in range(2):
            response = self.client.post(reverse("receipt-review", args=[receipt.pk]), self.review_data())
            self.assertEqual(response.status_code, 302, response.content)
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, "ready")
        self.assertEqual(receipt.purchases.count(), 1)

    def test_invalid_edit_keeps_previous_purchases_intact(self):
        receipt = self.upload()
        self.process(receipt)
        response = self.client.post(reverse("receipt-review", args=[receipt.pk]), self.review_data(goods_total="20"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["errors"])
        receipt.refresh_from_db()
        self.assertEqual(receipt.goods_total, Decimal("10.00"))
        self.assertEqual(receipt.purchases.get().total, Decimal("10.00"))

    def test_edit_to_existing_receipt_preserves_both_originals(self):
        first, second = self.upload(), self.upload("red")
        self.process(first)
        self.process(second, sample_receipt(receipt_number="CR-OTHER"))
        response = self.client.post(reverse("receipt-review", args=[second.pk]), self.review_data())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["errors"])
        second.refresh_from_db()
        self.assertEqual(second.receipt_number, "CR-OTHER")
        self.assertEqual(Purchase.objects.count(), 2)

    def test_original_download_requires_permission_and_is_not_cached(self):
        receipt = self.upload()
        url = reverse("receipt-original", args=[receipt.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(b"".join(response.streaming_content), photo().read())
        response = self.client.get(url, {"inline": "1"})
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertFalse(response["Content-Disposition"].startswith("attachment"))
        response.close()
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        user = get_user_model().objects.create_user("no-access")
        self.client.force_login(user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(reverse("receipt-upload"), {"image": photo()}).status_code, 403)

    def test_ready_items_cannot_be_edited_or_deleted_individually(self):
        receipt = self.upload()
        self.process(receipt)
        item = receipt.purchases.get()
        for route in ("purchase-update", "purchase-delete"):
            response = self.client.post(reverse(route, args=[item.pk]), {})
            self.assertRedirects(response, reverse("receipt-review", args=[receipt.pk]), fetch_redirect_response=False)
        self.assertTrue(Purchase.objects.filter(pk=item.pk).exists())

    def test_deleting_receipt_removes_lines_and_private_file_after_commit(self):
        receipt = self.upload()
        self.process(receipt)
        path = Path(receipt.source_file.path)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("receipt-delete", args=[receipt.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PurchaseReceipt.objects.exists())
        self.assertFalse(Purchase.objects.exists())
        self.assertFalse(path.exists())

    def test_pages_render_and_key_never_leaks(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "never-render-this-secret"}):
            response = self.client.get(reverse("receipt-upload"))
        self.assertContains(response, 'multiple required')
        self.assertNotContains(response, "never-render-this-secret")
        receipt = self.upload()
        self.assertEqual(self.client.get(reverse("receipt-review", args=[receipt.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:valdyti_purchasereceipt_change", args=[receipt.pk])).status_code, 200)
