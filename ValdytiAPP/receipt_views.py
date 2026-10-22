import hashlib
import logging
import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from .models import PurchaseReceipt
from .receipt_forms import ReceiptDetailsForm, ReceiptLineFormSet, ReceiptUploadForm
from .receipt_parser import ReceiptParserError, inspect_receipt_image, normalized_receipt, parse_receipt_image
from .receipt_service import ReceiptSaveError, expire_processing_receipts, include_receipt, json_values, validate_receipt_lines

logger = logging.getLogger(__name__)


def receipt_json(receipt):
    return {
        "id": receipt.pk, "filename": receipt.original_filename, "status": receipt.status,
        "label": receipt.get_status_display(), "date": receipt.purchase_date.isoformat() if receipt.purchase_date else "",
        "message": receipt.error_message or " ".join(receipt.warnings),
        "process_url": reverse("receipt-process", args=[receipt.pk]),
        "review_url": reverse("receipt-review", args=[receipt.pk]),
        "original_url": reverse("receipt-original", args=[receipt.pk]),
        "status_url": reverse("receipt-status", args=[receipt.pk]),
        "cancel_url": reverse("receipt-cancel", args=[receipt.pk]),
        "attempt": receipt.processing_attempt,
    }


class ReceiptUploadView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "valdyti.add_purchase"

    def get(self, request):
        expire_processing_receipts()
        return render(request, "ValdytiAPP/pirkimai/receipt_upload.html", {
            "receipts": PurchaseReceipt.objects.all()[:60], "max_files": settings.RECEIPT_BATCH_MAX_FILES,
            "max_mb": settings.RECEIPT_UPLOAD_MAX_BYTES // 1024 // 1024,
            "max_bytes": settings.RECEIPT_UPLOAD_MAX_BYTES,
            "api_configured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        })

    def post(self, request):
        if len(request.FILES.getlist("image")) != 1:
            return JsonResponse({"error": "Vienoje užklausoje siųskite vieną nuotrauką."}, status=400)
        form = ReceiptUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            return JsonResponse({"error": " ".join(error for errors in form.errors.values() for error in errors)}, status=400)
        upload = form.cleaned_data["image"]
        content = upload.read()
        digest = hashlib.sha256(content).hexdigest()
        expire_processing_receipts(PurchaseReceipt.objects.filter(file_hash=digest))
        existing = PurchaseReceipt.objects.filter(file_hash=digest).first()
        if existing:
            return JsonResponse({**receipt_json(existing), "existing": True})
        extension = inspect_receipt_image(content)
        receipt = PurchaseReceipt(file_hash=digest, original_filename=Path(upload.name).name[:255], created_by=request.user)
        stored_name = ""
        try:
            receipt.source_file.save("receipt" + extension, ContentFile(content), save=False)
            stored_name = receipt.source_file.name
            with transaction.atomic():
                receipt.save()
        except Exception as exc:
            if stored_name:
                receipt.source_file.storage.delete(stored_name)
            if isinstance(exc, IntegrityError):
                existing = PurchaseReceipt.objects.filter(file_hash=digest).first()
                if existing:
                    return JsonResponse({**receipt_json(existing), "existing": True})
            raise
        return JsonResponse({**receipt_json(receipt), "existing": False}, status=201)


class ReceiptProcessView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "valdyti.add_purchase"

    def post(self, request, pk):
        with transaction.atomic():
            expire_processing_receipts(PurchaseReceipt.objects.filter(pk=pk))
            receipt = get_object_or_404(PurchaseReceipt.objects.select_for_update(), pk=pk)
            expected_attempt = request.POST.get("expected_attempt")
            if expected_attempt is not None and expected_attempt != str(receipt.processing_attempt):
                return JsonResponse({**receipt_json(receipt), "message": "Čekio būsena pasikeitė. Nuskaitymas nepradėtas."}, status=409)
            if receipt.status in {PurchaseReceipt.Status.READY, PurchaseReceipt.Status.DUPLICATE, PurchaseReceipt.Status.REVIEW}:
                return JsonResponse(receipt_json(receipt))
            if (receipt.status == PurchaseReceipt.Status.PROCESSING and receipt.processing_started_at
                    and receipt.processing_started_at > timezone.now() - timedelta(minutes=5)):
                return JsonResponse({**receipt_json(receipt), "message": "Čekis jau nuskaitomas. Palaukite ir atnaujinkite sąrašą."}, status=409)
            receipt.status = PurchaseReceipt.Status.PROCESSING
            receipt.processing_started_at = timezone.now()
            receipt.processing_attempt += 1
            receipt.error_message = ""
            receipt.save()
            attempt = receipt.processing_attempt
        try:
            with receipt.source_file.open("rb") as stream:
                content = stream.read()
            raw, model = parse_receipt_image(content)
            metadata, rows, issues = normalized_receipt(raw)
            with transaction.atomic():
                receipt = PurchaseReceipt.objects.select_for_update().filter(pk=pk).first()
                if receipt is None:
                    return JsonResponse({"error": "Čekis ištrintas. Nuskaitymo rezultatas neįtrauktas."}, status=410)
                if receipt.processing_attempt != attempt or receipt.status != PurchaseReceipt.Status.PROCESSING:
                    return JsonResponse(receipt_json(receipt))
                for key, value in metadata.items():
                    setattr(receipt, key, value)
                receipt.raw_extraction, receipt.parser_model = raw, model
                receipt.extracted_lines = json_values(rows)
                issues += validate_receipt_lines(receipt, rows)
                receipt.warnings = list(dict.fromkeys(issues))
                receipt.status = PurchaseReceipt.Status.REVIEW
                receipt.processing_started_at = None
                receipt.save()
                if not receipt.warnings:
                    include_receipt(receipt, rows)
            return JsonResponse(receipt_json(receipt))
        except (ReceiptParserError, ReceiptSaveError, OSError) as exc:
            error = str(exc) if not isinstance(exc, OSError) else "Nepavyko perskaityti išsaugoto failo. Įkelkite nuotrauką iš naujo."
        except Exception:
            logger.exception("Receipt processing failed for receipt %s", pk)
            error = "Nuskaitymas nutrūko. Nuotrauka išsaugota; bandykite dar kartą."
        PurchaseReceipt.objects.filter(pk=pk, processing_attempt=attempt, status=PurchaseReceipt.Status.PROCESSING).update(
            status=PurchaseReceipt.Status.FAILED, processing_started_at=None, updated_at=timezone.now(), error_message=error)
        receipt = PurchaseReceipt.objects.filter(pk=pk).first()
        if receipt is None:
            return JsonResponse({"error": "Čekis ištrintas. Nuskaitymo rezultatas neįtrauktas."}, status=410)
        return JsonResponse(receipt_json(receipt), status=422)


class ReceiptStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "valdyti.view_purchase"

    def get(self, request, pk):
        expire_processing_receipts(PurchaseReceipt.objects.filter(pk=pk))
        response = JsonResponse(receipt_json(get_object_or_404(PurchaseReceipt, pk=pk)))
        response["Cache-Control"] = "private, no-store"
        return response


class ReceiptCancelView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "valdyti.add_purchase"

    def post(self, request, pk):
        with transaction.atomic():
            receipt = get_object_or_404(PurchaseReceipt.objects.select_for_update(), pk=pk)
            if receipt.status in {PurchaseReceipt.Status.PROCESSING, PurchaseReceipt.Status.UPLOADED}:
                receipt.processing_attempt += 1
                receipt.processing_started_at = None
                receipt.status = PurchaseReceipt.Status.FAILED
                receipt.error_message = "Nuskaitymas atšauktas. Originalas išsaugotas; vėliau gautas AI atsakymas nebus įtrauktas."
                receipt.save()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(receipt_json(receipt))
        messages.info(request, receipt.error_message or "Čekis šiuo metu nenuskaitomas; duomenys nepakeisti.")
        return redirect("receipt-review", pk=pk)


class ReceiptReviewView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "valdyti.view_purchase"

    def render(self, request, receipt, form=None, formset=None, errors=None):
        initial = list(receipt.purchases.values("name", "category", "quantity", "unit", "unit_price", "total", "notes"))
        return render(request, "ValdytiAPP/pirkimai/receipt_review.html", {
            "receipt": receipt, "form": form if form is not None else ReceiptDetailsForm(instance=receipt),
            "formset": formset if formset is not None else ReceiptLineFormSet(initial=initial or receipt.extracted_lines, prefix="lines"),
            "errors": errors or [],
            "can_edit": request.user.has_perm("valdyti.change_purchase" if receipt.status == PurchaseReceipt.Status.READY
                                               else "valdyti.add_purchase"),
        })

    def get(self, request, pk):
        expire_processing_receipts(PurchaseReceipt.objects.filter(pk=pk))
        return self.render(request, get_object_or_404(PurchaseReceipt, pk=pk))

    def post(self, request, pk):
        with transaction.atomic():
            expire_processing_receipts(PurchaseReceipt.objects.filter(pk=pk))
            receipt = get_object_or_404(PurchaseReceipt.objects.select_for_update(), pk=pk)
            required = "valdyti.change_purchase" if receipt.status == PurchaseReceipt.Status.READY else "valdyti.add_purchase"
            if not request.user.has_perm(required):
                return self.handle_no_permission()
            if receipt.status in {PurchaseReceipt.Status.PROCESSING, PurchaseReceipt.Status.DUPLICATE}:
                return self.render(request, receipt, errors=["Šio čekio dabar redaguoti negalima."])
            form = ReceiptDetailsForm(request.POST, instance=receipt)
            formset = ReceiptLineFormSet(request.POST, prefix="lines")
            if form.is_valid() and formset.is_valid():
                receipt = form.save(commit=False)
                rows = [{key: value for key, value in line.cleaned_data.items() if key != "DELETE"}
                        for line in formset if line.cleaned_data and not line.cleaned_data.get("DELETE")]
                errors = validate_receipt_lines(receipt, rows)
                if not errors:
                    receipt.extracted_lines, receipt.warnings = json_values(rows), []
                    try:
                        include_receipt(receipt, rows, replace=True)
                    except ReceiptSaveError as exc:
                        errors = [str(exc)]
                    else:
                        messages.success(request, "Čekis ir pirkimai išsaugoti." if receipt.status == PurchaseReceipt.Status.READY
                                         else receipt.error_message)
                        return redirect("receipt-review", pk=receipt.pk)
                return self.render(request, receipt, form, formset, errors)
            return self.render(request, receipt, form, formset)


class ReceiptOriginalView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "valdyti.view_purchase"

    def get(self, request, pk):
        receipt = get_object_or_404(PurchaseReceipt, pk=pk)
        try:
            inline = request.GET.get("inline") == "1"
            content_type = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(
                Path(receipt.source_file.name).suffix.lower(), "application/octet-stream")
            response = FileResponse(receipt.source_file.open("rb"), as_attachment=not inline,
                                    filename=receipt.original_filename,
                                    content_type=content_type if inline else "application/octet-stream")
        except (OSError, ValueError) as exc:
            raise Http404("Originalas nerastas.") from exc
        response["Cache-Control"] = "private, no-store"
        return response


class ReceiptDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "valdyti.delete_purchase"

    def post(self, request, pk):
        with transaction.atomic():
            receipt = get_object_or_404(PurchaseReceipt.objects.select_for_update(), pk=pk)
            storage, name = receipt.source_file.storage, receipt.source_file.name
            receipt.delete()
            transaction.on_commit(lambda: storage.delete(name))
        messages.success(request, "Čekis, originalas ir jo pirkimo eilutės pašalinti.")
        return redirect("receipt-upload")
