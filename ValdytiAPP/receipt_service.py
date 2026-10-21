import hashlib
import json
import re
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction

from .models import Purchase, PurchaseReceipt


class ReceiptSaveError(Exception):
    pass


def json_values(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def normalized_id(value):
    return re.sub(r"[^\w]", "", value.casefold(), flags=re.UNICODE).replace("_", "")


def receipt_business_key(receipt):
    if not receipt.purchase_date or not receipt.receipt_number:
        return None
    seller = receipt.store if receipt.store != "other" else normalized_id(receipt.store_name)
    if not seller:
        return None
    value = f"{seller}|{receipt.purchase_date.isoformat()}|{normalized_id(receipt.receipt_number)}"
    return hashlib.sha256(value.encode()).hexdigest()


def old_manual_duplicate(receipt):
    if not receipt.receipt_number or not receipt.purchase_date:
        return False
    number = normalized_id(receipt.receipt_number).lstrip("0")
    if not number:
        return False
    day_suffix = receipt.purchase_date.strftime("%Y%m%d")
    for value in Purchase.objects.filter(receipt__isnull=True, purchase_date=receipt.purchase_date,
                                         store=receipt.store).values_list("receipt_reference", flat=True):
        previous = normalized_id(value).lstrip("0")
        if previous in {number, number + day_suffix}:
            return True
    return False


def validate_receipt_lines(receipt, rows):
    issues = []
    if not receipt.purchase_date or not receipt.store:
        issues.append("Nurodykite čekio datą ir parduotuvę.")
    if not rows:
        issues.append("Pridėkite bent vieną prekę.")
    if receipt.goods_total is None or receipt.paid_total is None:
        issues.append("Nurodykite prekių ir sumokėtą sumas.")
    else:
        if any(row.get("total") is None for row in rows):
            issues.append("Nurodykite visų prekių sumas.")
        else:
            total = sum((row["total"] for row in rows), Decimal("0"))
            if total != receipt.goods_total:
                issues.append(f"Prekių eilutės: {total:.2f} €, čekio prekių suma: {receipt.goods_total:.2f} €.")
        if receipt.goods_total + receipt.payment_adjustment != receipt.paid_total:
            issues.append("Prekių suma + mokėjimo korekcija turi sutapti su sumokėta suma.")
    for index, row in enumerate(rows):
        item = Purchase(**row, purchase_date=receipt.purchase_date, store=receipt.store,
                        receipt_reference=receipt.receipt_number)
        if index == 0:
            item.payment_adjustment = receipt.payment_adjustment
        try:
            item.full_clean(exclude=["receipt"])
        except ValidationError as exc:
            issues.append(f"{index + 1} eilutė: {'; '.join(exc.messages)}")
    return list(dict.fromkeys(issues))


def include_receipt(receipt, rows, *, replace=False):
    """Caller holds the receipt row lock. Import either every row or none."""
    issues = validate_receipt_lines(receipt, rows)
    if issues:
        raise ReceiptSaveError(" ".join(issues))
    key = receipt_business_key(receipt)
    duplicate = PurchaseReceipt.objects.filter(business_key=key).exclude(pk=receipt.pk).first() if key else None
    if duplicate or old_manual_duplicate(receipt):
        if receipt.purchases.exists():
            raise ReceiptSaveError("Toks čekis jau įtrauktas. Pakeitimai neišsaugoti; ankstesni pirkimai palikti.")
        receipt.status = PurchaseReceipt.Status.DUPLICATE
        receipt.duplicate_of = duplicate
        receipt.business_key = None
        receipt.error_message = "Šis čekis jau yra pirkimuose. Antrą kartą prekės neįtrauktos."
        receipt.save()
        return
    if receipt.purchases.exists() and not replace:
        return
    try:
        with transaction.atomic():
            receipt.business_key = key
            receipt.status = PurchaseReceipt.Status.READY
            receipt.error_message = ""
            receipt.save()
            if replace:
                receipt.purchases.all().delete()
            purchases = []
            for index, row in enumerate(rows):
                purchases.append(Purchase(
                    **row, receipt=receipt, purchase_date=receipt.purchase_date, store=receipt.store,
                    receipt_reference=receipt.receipt_number,
                    payment_adjustment=receipt.payment_adjustment if index == 0 else Decimal("0")))
            Purchase.objects.bulk_create(purchases)
    except IntegrityError as exc:
        # A concurrently uploaded different photo of the same numbered receipt won the unique key.
        duplicate = PurchaseReceipt.objects.filter(business_key=key).exclude(pk=receipt.pk).first() if key else None
        if not duplicate:
            raise exc
        if receipt.purchases.exists():
            raise ReceiptSaveError("Toks čekis jau įtrauktas. Pakeitimai neišsaugoti; ankstesni pirkimai palikti.") from exc
        receipt.business_key = None
        receipt.duplicate_of = duplicate
        receipt.status = PurchaseReceipt.Status.DUPLICATE
        receipt.error_message = "Šis čekis ką tik įtrauktas iš kitos nuotraukos. Dublikatas praleistas."
        receipt.save()
