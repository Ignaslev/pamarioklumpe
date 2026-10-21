"""Import reviewed receipt transcriptions; validate totals before writing anything."""
import json
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ValdytiAPP.models import Purchase


class Command(BaseCommand):
    help = "Import reviewed purchase-receipt JSON. Existing receipt references are never overwritten."

    def add_arguments(self, parser):
        parser.add_argument("file")
        parser.add_argument("--dry-run", action="store_true")

    @staticmethod
    def signature(item):
        return (item.purchase_date, item.store, item.category, item.name, item.quantity,
                item.unit, item.unit_price, item.total, item.payment_adjustment)

    def handle(self, *args, **options):
        try:
            receipts = json.loads(Path(options["file"]).read_text(encoding="utf-8"))["receipts"]
            batches = []
            seen = set()
            for receipt in receipts:
                day = date.fromisoformat(receipt["date"])
                reference = receipt["reference"]
                key = (day, receipt["store"], reference)
                if not reference.strip() or key in seen:
                    raise CommandError("Empty or repeated receipt reference in import file.")
                seen.add(key)
                rows = []
                for index, data in enumerate(receipt["items"]):
                    notes = [f"Šaltinis: {receipt.get('source_filename', '')}", receipt.get("notes", ""), data.get("notes", "")]
                    item = Purchase(
                        purchase_date=day, store=receipt["store"], receipt_reference=reference,
                        category=data["category"], name=data["name"], unit=data.get("unit", ""),
                        quantity=Decimal(data["quantity"]) if data.get("quantity") is not None else None,
                        unit_price=Decimal(data["unit_price"]) if data.get("unit_price") is not None else None,
                        total=Decimal(data["total"]),
                        payment_adjustment=Decimal(receipt.get("payment_adjustment", "0")) if index == 0 else Decimal("0"),
                        notes="\n".join(note for note in notes if note),
                    )
                    item.full_clean()
                    rows.append(item)
                goods = sum((row.total for row in rows), Decimal("0"))
                paid = sum((row.total + row.payment_adjustment for row in rows), Decimal("0"))
                if not rows or goods != Decimal(receipt["goods_total"]) or paid != Decimal(receipt["paid_total"]):
                    raise CommandError(f"Receipt {reference}: calculated goods={goods}, paid={paid}; expected goods={receipt['goods_total']}, paid={receipt['paid_total']}.")
                batches.append((key, rows, goods, paid))
        except (KeyError, ValueError, TypeError, InvalidOperation, ValidationError, OSError) as exc:
            raise CommandError(str(exc)) from exc

        created = skipped = 0
        with transaction.atomic():
            for (day, store, reference), rows, goods, paid in batches:
                existing = list(Purchase.objects.filter(purchase_date=day, store=store, receipt_reference=reference))
                if existing:
                    if Counter(map(self.signature, existing)) != Counter(map(self.signature, rows)):
                        raise CommandError(f"Receipt {reference} already exists with different data. Import cancelled; no records changed.")
                    skipped += len(existing)
                elif not options["dry_run"]:
                    Purchase.objects.bulk_create(rows)
                    created += len(rows)
                self.stdout.write(f"{reference}: {len(rows)} lines; goods {goods:.2f}; paid {paid:.2f}")
        self.stdout.write(self.style.SUCCESS(f"Validated {len(batches)} receipts. Created {created}; already present {skipped}."))
