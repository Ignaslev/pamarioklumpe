from django import forms
from django.forms import formset_factory

from .models import Purchase, PurchaseReceipt


class ReceiptUploadForm(forms.Form):
    image = forms.FileField(label="Čekio nuotrauka")

    def clean_image(self):
        from django.conf import settings
        from .receipt_parser import inspect_receipt_image, ReceiptParserError

        uploaded = self.cleaned_data["image"]
        if uploaded.size > settings.RECEIPT_UPLOAD_MAX_BYTES:
            raise forms.ValidationError(f"Nuotrauka per didelė. Riba: {settings.RECEIPT_UPLOAD_MAX_BYTES // 1024 // 1024} MB.")
        try:
            inspect_receipt_image(uploaded.read())
        except ReceiptParserError as exc:
            raise forms.ValidationError(str(exc)) from exc
        finally:
            uploaded.seek(0)
        return uploaded


class ReceiptDetailsForm(forms.ModelForm):
    class Meta:
        model = PurchaseReceipt
        fields = ("purchase_date", "store", "store_name", "store_address", "receipt_number",
                  "goods_total", "paid_total", "payment_adjustment")
        widgets = {"purchase_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
            if name in {"purchase_date", "store", "goods_total", "paid_total"}:
                field.required = True

    def clean(self):
        cleaned = super().clean()
        for name in ("goods_total", "paid_total"):
            if cleaned.get(name) is not None and cleaned[name] < 0:
                self.add_error(name, "Suma negali būti neigiama.")
        return cleaned


class ReceiptLineForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ("name", "category", "quantity", "unit", "unit_price", "total", "notes")
        widgets = {"notes": forms.TextInput(),
                   "quantity": forms.NumberInput(attrs={"step": "0.001", "min": "0.001"}),
                   "unit_price": forms.NumberInput(attrs={"step": "0.0001", "min": "0"}),
                   "total": forms.NumberInput(attrs={"step": "0.01", "min": "0"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


ReceiptLineFormSet = formset_factory(ReceiptLineForm, extra=1, can_delete=True,
                                     max_num=500, validate_max=True, absolute_max=501)
