from django.db import models


class Worker(models.Model):
    first_name = models.CharField("Vardas", max_length=80)
    last_name = models.CharField("Pavardė", max_length=80)
    job_title = models.CharField("Pareigos", max_length=120)
    phone = models.CharField("Telefono numeris", max_length=30, blank=True)
    email = models.EmailField("El. paštas", blank=True)
    notes = models.TextField("Pastabos", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("last_name", "first_name")
        verbose_name = "Darbuotojas"
        verbose_name_plural = "Darbuotojai"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class MenuCategory(models.Model):
    name = models.CharField("Pavadinimas", max_length=120, unique=True)
    parent = models.ForeignKey(
        "self",
        verbose_name="Pagrindinė kategorija",
        on_delete=models.PROTECT,
        related_name="subcategories",
        blank=True,
        null=True,
    )
    sort_order = models.PositiveIntegerField("Rikiavimo eilė", default=0)
    is_active = models.BooleanField("Rodoma meniu", default=True)

    class Meta:
        ordering = ("parent__sort_order", "parent__name", "sort_order", "name")
        verbose_name = "Meniu kategorija"
        verbose_name_plural = "Meniu kategorijos"

    def __str__(self):
        if self.parent:
            return f"{self.parent} → {self.name}"
        return self.name

    def clean(self):
        super().clean()
        category = self.parent
        while category:
            if category.pk == self.pk:
                from django.core.exceptions import ValidationError

                raise ValidationError({"parent": "Kategorija negali būti savo pačios subkategorija."})
            category = category.parent


class MenuItem(models.Model):
    category = models.ForeignKey(
        MenuCategory,
        verbose_name="Kategorija",
        on_delete=models.PROTECT,
        related_name="items",
    )
    name = models.CharField("Patiekalo pavadinimas", max_length=160)
    description = models.TextField("Aprašymas", blank=True)
    price = models.DecimalField("Pirma kaina (€)", max_digits=7, decimal_places=2, blank=True, null=True)
    second_price = models.DecimalField("Antra kaina (€)", max_digits=7, decimal_places=2, blank=True, null=True)
    sort_order = models.PositiveIntegerField("Rikiavimo eilė", default=0)
    is_active = models.BooleanField("Rodomas meniu", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("category__sort_order", "category__name", "sort_order", "name")
        verbose_name = "Meniu patiekalas"
        verbose_name_plural = "Meniu patiekalai"

    def __str__(self):
        return self.name


class Invoice(models.Model):
    """A supplier invoice and the original PDF it was read from."""

    source_file = models.FileField("Originalus PDF", upload_to="invoices/%Y/%m/")
    original_filename = models.CharField("Originalus failo pavadinimas", max_length=255)
    file_hash = models.CharField("PDF SHA-256 piršto atspaudas", max_length=64, unique=True, db_index=True)

    invoice_number = models.CharField("Sąskaitos numeris", max_length=100, blank=True)
    invoice_date = models.DateField("Sąskaitos data", blank=True, null=True)
    due_date = models.DateField("Apmokėjimo terminas", blank=True, null=True)
    supplier_name = models.CharField("Tiekėjas", max_length=255, blank=True)
    supplier_company_code = models.CharField("Tiekėjo įmonės kodas", max_length=80, blank=True)
    supplier_vat_id = models.CharField("Tiekėjo PVM kodas", max_length=80, blank=True)
    supplier_address = models.TextField("Tiekėjo adresas", blank=True)
    buyer_name = models.CharField("Pirkėjas", max_length=255, blank=True)
    buyer_company_code = models.CharField("Pirkėjo įmonės kodas", max_length=80, blank=True)
    buyer_vat_id = models.CharField("Pirkėjo PVM kodas", max_length=80, blank=True)
    buyer_address = models.TextField("Pirkėjo adresas", blank=True)
    subtotal = models.DecimalField("Suma be PVM", max_digits=12, decimal_places=2, blank=True, null=True)
    vat_rate = models.DecimalField("PVM tarifas (%)", max_digits=5, decimal_places=2, blank=True, null=True)
    vat_amount = models.DecimalField("PVM suma", max_digits=12, decimal_places=2, blank=True, null=True)
    total = models.DecimalField("Bendra suma", max_digits=12, decimal_places=2, blank=True, null=True)
    currency = models.CharField("Valiuta", max_length=3, default="EUR")
    notes = models.TextField("Pastabos", blank=True)
    raw_extraction = models.JSONField("Nuskaityti duomenys", default=dict, blank=True)
    parser_model = models.CharField("Nuskaitymo modelis", max_length=100, blank=True)
    created_by = models.ForeignKey(
        "auth.User",
        verbose_name="Įkėlė",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_invoices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-invoice_date", "-created_at")
        verbose_name = "Sąskaita"
        verbose_name_plural = "Sąskaitos"

    def __str__(self):
        return self.invoice_number or self.original_filename


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        verbose_name="Sąskaita",
        on_delete=models.CASCADE,
        related_name="lines",
    )
    line_number = models.PositiveIntegerField("Eilutės numeris", default=0)
    product_code = models.CharField("Prekės kodas", max_length=100, blank=True)
    name = models.CharField("Prekė ar paslauga", max_length=500)
    unit = models.CharField("Vienetas", max_length=30, blank=True)
    quantity = models.DecimalField("Kiekis", max_digits=12, decimal_places=3, blank=True, null=True)
    unit_price = models.DecimalField("Vieneto kaina be PVM", max_digits=12, decimal_places=4, blank=True, null=True)
    total = models.DecimalField("Eilutės suma be PVM", max_digits=12, decimal_places=2, blank=True, null=True)

    class Meta:
        ordering = ("line_number", "pk")
        verbose_name = "Sąskaitos eilutė"
        verbose_name_plural = "Sąskaitos eilutės"

    def __str__(self):
        return self.name
