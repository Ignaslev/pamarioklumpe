"""Structured PDF invoice reading through the OpenAI Responses API."""

import base64
import json
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation


class InvoiceParserError(Exception):
    """A message that can safely be shown to a management user."""


INVOICE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["invoice", "lines"],
    "properties": {
        "invoice": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "invoice_number", "invoice_date", "due_date", "supplier_name", "supplier_company_code",
                "supplier_vat_id", "supplier_address", "buyer_name", "buyer_company_code", "buyer_vat_id",
                "buyer_address", "subtotal", "vat_rate", "vat_amount", "total", "currency",
            ],
            "properties": {
                "invoice_number": {"type": ["string", "null"]},
                "invoice_date": {"type": ["string", "null"]},
                "due_date": {"type": ["string", "null"]},
                "supplier_name": {"type": ["string", "null"]},
                "supplier_company_code": {"type": ["string", "null"]},
                "supplier_vat_id": {"type": ["string", "null"]},
                "supplier_address": {"type": ["string", "null"]},
                "buyer_name": {"type": ["string", "null"]},
                "buyer_company_code": {"type": ["string", "null"]},
                "buyer_vat_id": {"type": ["string", "null"]},
                "buyer_address": {"type": ["string", "null"]},
                "subtotal": {"type": ["number", "null"]},
                "vat_rate": {"type": ["number", "null"]},
                "vat_amount": {"type": ["number", "null"]},
                "total": {"type": ["number", "null"]},
                "currency": {"type": ["string", "null"]},
            },
        },
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["line_number", "product_code", "name", "unit", "quantity", "unit_price", "total"],
                "properties": {
                    "line_number": {"type": ["integer", "null"]},
                    "product_code": {"type": ["string", "null"]},
                    "name": {"type": ["string", "null"]},
                    "unit": {"type": ["string", "null"]},
                    "quantity": {"type": ["number", "null"]},
                    "unit_price": {"type": ["number", "null"]},
                    "total": {"type": ["number", "null"]},
                },
            },
        },
    },
}


def parse_invoice_pdf(pdf_bytes: bytes, filename: str) -> tuple[dict, str]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise InvoiceParserError("Automatiniam sąskaitos nuskaitymui reikia nustatyti OPENAI_API_KEY serverio .env faile.")

    try:
        from openai import APIError, OpenAI
    except ImportError as exc:
        raise InvoiceParserError("Trūksta OpenAI bibliotekos. Įdiekite projekto requirements.") from exc

    model = os.getenv("OPENAI_INVOICE_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    prompt = """You read Lithuanian and international supplier invoices. Extract the invoice exactly as shown.
Return every visible item line. Amounts must be numeric without currency symbols and dates must use YYYY-MM-DD.
Use null when a field is absent or cannot be read. Do not invent values. `subtotal`, each line `unit_price`,
and each line `total` should be excluding VAT when the invoice makes that distinction clear. Currency is a
three-letter code, normally EUR. Preserve codes and document numbers exactly."""
    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_file",
                        "filename": filename,
                        "file_data": "data:application/pdf;base64," + base64.b64encode(pdf_bytes).decode("ascii"),
                    },
                ],
            }],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "invoice_extraction",
                    "strict": True,
                    "schema": INVOICE_SCHEMA,
                }
            },
        )
        return json.loads(response.output_text), model
    except APIError as exc:
        status_code = getattr(exc, "status_code", None)
        status = f" (HTTP {status_code})" if status_code else ""
        detail = str(exc).strip() or "be papildomos informacijos"
        raise InvoiceParserError(f"AI paslaugos atsakymas{status}: {detail}") from exc
    except (json.JSONDecodeError, AttributeError) as exc:
        raise InvoiceParserError("PDF nuskaitymas negrąžino tinkamų duomenų. Bandykite kitą sąskaitos kopiją.") from exc


def text_value(value, max_length=None) -> str:
    result = str(value or "").strip()
    return result[:max_length] if max_length else result


def decimal_value(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def date_value(value):
    if not value:
        return None
    string_value = str(value).strip()
    for format_string in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(string_value, format_string).date()
        except ValueError:
            continue
    return None


def cleaned_invoice_data(data: dict) -> tuple[dict, list[dict]]:
    invoice = data.get("invoice") or {}
    cleaned_invoice = {
        "invoice_number": text_value(invoice.get("invoice_number"), 100),
        "invoice_date": date_value(invoice.get("invoice_date")),
        "due_date": date_value(invoice.get("due_date")),
        "supplier_name": text_value(invoice.get("supplier_name"), 255),
        "supplier_company_code": text_value(invoice.get("supplier_company_code"), 80),
        "supplier_vat_id": text_value(invoice.get("supplier_vat_id"), 80),
        "supplier_address": text_value(invoice.get("supplier_address")),
        "buyer_name": text_value(invoice.get("buyer_name"), 255),
        "buyer_company_code": text_value(invoice.get("buyer_company_code"), 80),
        "buyer_vat_id": text_value(invoice.get("buyer_vat_id"), 80),
        "buyer_address": text_value(invoice.get("buyer_address")),
        "subtotal": decimal_value(invoice.get("subtotal")),
        "vat_rate": decimal_value(invoice.get("vat_rate")),
        "vat_amount": decimal_value(invoice.get("vat_amount")),
        "total": decimal_value(invoice.get("total")),
        "currency": text_value(invoice.get("currency"), 3).upper() or "EUR",
    }
    lines = []
    for index, line in enumerate(data.get("lines") or [], start=1):
        name = text_value(line.get("name"), 500)
        if not name:
            continue
        lines.append({
            "line_number": line.get("line_number") or index,
            "product_code": text_value(line.get("product_code"), 100),
            "name": name,
            "unit": text_value(line.get("unit"), 30),
            "quantity": decimal_value(line.get("quantity")),
            "unit_price": decimal_value(line.get("unit_price")),
            "total": decimal_value(line.get("total")),
        })
    return cleaned_invoice, lines
