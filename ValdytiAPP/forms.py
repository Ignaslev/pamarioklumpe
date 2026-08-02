from django import forms

from .models import Invoice, InvoiceLine, MenuCategory, MenuItem, Worker, normalize_chip_uid


class WorkerForm(forms.ModelForm):
    class Meta:
        model = Worker
        fields = ("first_name", "last_name", "job_title", "phone", "email", "chip_uid", "notes")
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_chip_uid(self):
        return normalize_chip_uid(self.cleaned_data.get("chip_uid"))


class MenuCategoryForm(forms.ModelForm):
    class Meta:
        model = MenuCategory
        fields = ("name", "parent", "sort_order", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parent"].queryset = MenuCategory.objects.exclude(pk=self.instance.pk).order_by("name")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "checkbox-control" if isinstance(field.widget, forms.CheckboxInput) else "form-control")


class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ("category", "name", "description", "price", "second_price", "sort_order", "is_active")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "price": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "second_price": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = MenuCategory.objects.filter(is_active=True).order_by("name")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "checkbox-control" if isinstance(field.widget, forms.CheckboxInput) else "form-control")


class InvoiceUploadForm(forms.Form):
    pdf = forms.FileField(label="Sąskaitos PDF", widget=forms.ClearableFileInput(attrs={"accept": "application/pdf"}))

    def __init__(self, *args, max_bytes=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_bytes = max_bytes
        self.fields["pdf"].widget.attrs["class"] = "form-control"

    def clean_pdf(self):
        uploaded_file = self.cleaned_data["pdf"]
        uploaded_file.seek(0)
        header = uploaded_file.read(1024)
        uploaded_file.seek(0)
        if not uploaded_file.name.lower().endswith(".pdf") or b"%PDF-" not in header:
            raise forms.ValidationError("Įkelkite PDF failą.")
        if self.max_bytes and uploaded_file.size > self.max_bytes:
            raise forms.ValidationError(f"PDF failas per didelis. Didžiausias dydis: {self.max_bytes // 1024 // 1024} MB.")
        return uploaded_file


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = (
            "invoice_number", "invoice_date", "due_date", "supplier_name", "supplier_company_code",
            "supplier_vat_id", "supplier_address", "buyer_name", "buyer_company_code", "buyer_vat_id",
            "buyer_address", "subtotal", "vat_rate", "vat_amount", "total", "currency", "notes",
        )
        widgets = {
            "invoice_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "supplier_address": forms.Textarea(attrs={"rows": 3}),
            "buyer_address": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "subtotal": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "vat_rate": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "vat_amount": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "total": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "checkbox-control" if isinstance(field.widget, forms.CheckboxInput) else "form-control")


class InvoiceLineForm(forms.ModelForm):
    class Meta:
        model = InvoiceLine
        fields = ("line_number", "product_code", "name", "unit", "quantity", "unit_price", "total")
        widgets = {
            "quantity": forms.NumberInput(attrs={"step": "0.001", "min": "0"}),
            "unit_price": forms.NumberInput(attrs={"step": "0.0001", "min": "0"}),
            "total": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "checkbox-control" if isinstance(field.widget, forms.CheckboxInput) else "form-control")
