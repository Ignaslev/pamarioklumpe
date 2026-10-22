import hashlib
import logging
import json
import os
import re
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

from .models import PurchaseReceipt, PurchaseReceiptPart
from .receipt_forms import ReceiptDetailsForm, ReceiptLineFormSet, ReceiptUploadForm
from .receipt_parser import ReceiptParserError, inspect_receipt_image, normalized_receipt, parse_receipt_image, parse_receipt_parts
from .receipt_service import ReceiptSaveError, expire_processing_receipts, include_receipt, json_values, validate_receipt_lines

logger = logging.getLogger(__name__)


def receipt_json(receipt):
    complete = receipt.upload_complete
    return {
        "id": receipt.pk, "filename": receipt.original_filename, "status": receipt.status,
        "label": receipt.get_status_display(), "date": receipt.purchase_date.isoformat() if receipt.purchase_date else "",
        "message": receipt.error_message or (" ".join(receipt.warnings) if complete else
            f"Įkelta {receipt.parts.count()} iš {len(receipt.part_manifest)} dalių. Tęsimui antroje formoje pasirinkite visas tas pačias nuotraukas."),
        "process_url": reverse("receipt-process", args=[receipt.pk]),
        "review_url": reverse("receipt-review", args=[receipt.pk]),
        "original_url": reverse("receipt-original", args=[receipt.pk]),
        "status_url": reverse("receipt-status", args=[receipt.pk]),
        "cancel_url": reverse("receipt-cancel", args=[receipt.pk]),
        "attempt": receipt.processing_attempt,
        "upload_complete": complete,
        "part_count": len(receipt.part_manifest) or 1,
        "part_uploads": [{"hash": item["hash"], "url": reverse("receipt-part-upload", args=[receipt.pk, index])}
                         for index, item in enumerate(receipt.part_manifest, start=1)],
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
            if not receipt.upload_complete:
                return JsonResponse({**receipt_json(receipt), "message": "Įkeltos ne visos čekio dalys. Dar kartą pasirinkite visas to paties čekio nuotraukas antroje formoje."}, status=409)
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
            if receipt.part_manifest:
                parts = []
                for part in receipt.parts.all():
                    with part.source_file.open("rb") as stream:
                        parts.append(stream.read())
                raw, model = parse_receipt_parts(parts)
            else:
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
            "parts": receipt.parts.all(),
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
            if not receipt.upload_complete:
                return self.render(request, receipt, errors=["Trūksta čekio nuotraukų. Užbaikite įkėlimą antroje čekių įkėlimo formoje."])
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
        source, filename = receipt.source_file, receipt.original_filename
        if request.GET.get("part"):
            try:
                position = int(request.GET["part"])
            except ValueError as exc:
                raise Http404("Dalis nerasta.") from exc
            part = get_object_or_404(receipt.parts, position=position)
            source, filename = part.source_file, part.original_filename
        try:
            inline = request.GET.get("inline") == "1"
            content_type = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(
                Path(source.name).suffix.lower(), "application/octet-stream")
            response = FileResponse(source.open("rb"), as_attachment=not inline,
                                    filename=filename,
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
            files = {(part.source_file.storage, part.source_file.name) for part in receipt.parts.all()}
            if receipt.source_file.name:
                files.add((receipt.source_file.storage, receipt.source_file.name))
            receipt.delete()
            for storage, name in files:
                transaction.on_commit(lambda storage=storage, name=name: storage.delete(name))
        messages.success(request, "Čekis, originalas ir jo pirkimo eilutės pašalinti.")
        return redirect("receipt-upload")


class ReceiptMultipartCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "valdyti.add_purchase"

    def post(self, request):
        try:
            manifest = json.loads(request.POST.get("manifest", ""))
            if not isinstance(manifest, list) or not 2 <= len(manifest) <= 6:
                raise ValueError
            cleaned = []
            for item in manifest:
                if not isinstance(item, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("hash", ""))):
                    raise ValueError
                if type(item.get("size")) is not int or not 0 < item["size"] <= settings.RECEIPT_UPLOAD_MAX_BYTES:
                    raise ValueError
                cleaned.append({"hash": item["hash"], "size": item["size"], "name": Path(str(item.get("name") or "dalis.jpg")).name[:255]})
            if len({item["hash"] for item in cleaned}) != len(cleaned):
                return JsonResponse({"error": "Pasirinkta ta pati nuotrauka kelis kartus. Palikite tik skirtingas čekio dalis."}, status=400)
        except (ValueError, TypeError, KeyError):
            return JsonResponse({"error": "Vienam čekiui pasirinkite 2–6 JPG, PNG arba WEBP nuotraukas, kiekvieną iki 15 MB."}, status=400)
        # Identity is order independent: reselecting/reordering the same files resumes the same receipt.
        digest = hashlib.sha256(("multipart-v1:" + ":".join(sorted(item["hash"] for item in cleaned))).encode()).hexdigest()
        expire_processing_receipts(PurchaseReceipt.objects.filter(file_hash=digest))
        receipt, created = PurchaseReceipt.objects.get_or_create(file_hash=digest, defaults={
            "original_filename": f"Vienas čekis · {len(cleaned)} nuotraukos · {cleaned[0]['name']}"[:255],
            "part_manifest": cleaned, "created_by": request.user,
        })
        return JsonResponse({**receipt_json(receipt), "existing": not created}, status=201 if created else 200)


class ReceiptPartUploadView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "valdyti.add_purchase"

    def post(self, request, pk, position):
        if len(request.FILES.getlist("image")) != 1:
            return JsonResponse({"error": "Įkelkite vieną čekio dalį."}, status=400)
        form = ReceiptUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            return JsonResponse({"error": " ".join(error for errors in form.errors.values() for error in errors)}, status=400)
        upload = form.cleaned_data["image"]
        content = upload.read()
        digest = hashlib.sha256(content).hexdigest()
        stored_name, storage = "", None
        try:
            with transaction.atomic():
                receipt = get_object_or_404(PurchaseReceipt.objects.select_for_update(), pk=pk)
                if not receipt.part_manifest or not 1 <= position <= len(receipt.part_manifest):
                    return JsonResponse({"error": "Ši čekio dalis nenumatyta."}, status=400)
                expected = receipt.part_manifest[position - 1]
                if digest != expected["hash"] or len(content) != expected["size"]:
                    return JsonResponse({"error": "Nuotrauka neatitinka pasirinktos čekio dalies. Pasirinkite visas dalis iš naujo."}, status=400)
                existing = receipt.parts.filter(position=position).first()
                if existing:
                    return JsonResponse(receipt_json(receipt))
                if receipt.status not in {PurchaseReceipt.Status.UPLOADED, PurchaseReceipt.Status.FAILED}:
                    return JsonResponse({"error": "Nuskaitomo arba įtraukto čekio nuotraukų keisti negalima."}, status=409)
                part = PurchaseReceiptPart(receipt=receipt, position=position, original_filename=expected["name"], file_hash=digest)
                part.source_file.save("part" + inspect_receipt_image(content), ContentFile(content), save=False)
                stored_name, storage = part.source_file.name, part.source_file.storage
                part.save()
                if position == 1:
                    receipt.source_file.name = stored_name
                    receipt.save(update_fields=["source_file", "updated_at"])
                result = receipt_json(receipt)
        except Exception:
            if stored_name:
                storage.delete(stored_name)
            raise
        return JsonResponse(result, status=201)
