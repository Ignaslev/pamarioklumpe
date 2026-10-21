import re
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


def normalize_chip_uid(value):
    """Store RFID UIDs in one stable form regardless of spaces or separators."""
    value = (value or "").strip()
    if not value:
        return None
    if not re.fullmatch(r"[0-9A-Fa-f:\- ]+", value):
        raise ValidationError("Lusto UID gali sudaryti tik skaičiai, raidės A–F ir skirtukai.")
    normalized = re.sub(r"[:\- ]", "", value).upper()
    if len(normalized) < 8 or len(normalized) > 32 or len(normalized) % 2:
        raise ValidationError("Lusto UID turi būti 4–16 baitų šešioliktainis kodas.")
    return normalized


class Worker(models.Model):
    first_name = models.CharField("Vardas", max_length=80)
    last_name = models.CharField("Pavardė", max_length=80)
    job_title = models.CharField("Pareigos", max_length=120)
    phone = models.CharField("Telefono numeris", max_length=30, blank=True)
    email = models.EmailField("El. paštas", blank=True)
    chip_uid = models.CharField(
        "Lusto UID",
        max_length=32,
        unique=True,
        blank=True,
        null=True,
        help_text="RFID lusto kodas, pvz. 04A1B2C3. Tą patį lustą galima priskirti tik vienam darbuotojui.",
    )
    notes = models.TextField("Pastabos", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("last_name", "first_name")
        verbose_name = "Darbuotojas"
        verbose_name_plural = "Darbuotojai"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def clean(self):
        super().clean()
        self.chip_uid = normalize_chip_uid(self.chip_uid)

    def save(self, *args, **kwargs):
        self.chip_uid = normalize_chip_uid(self.chip_uid)
        return super().save(*args, **kwargs)


class AttendanceEvent(models.Model):
    class EventType(models.TextChoices):
        CLOCK_IN = "IN", "Atvyko"
        CLOCK_OUT = "OUT", "Išvyko"

    worker = models.ForeignKey(
        Worker,
        verbose_name="Darbuotojas",
        on_delete=models.SET_NULL,
        related_name="attendance_events",
        blank=True,
        null=True,
    )
    worker_name = models.CharField("Darbuotojo vardas nuskaitymo metu", max_length=170)
    chip_uid = models.CharField("Lusto UID", max_length=32, db_index=True)
    event_type = models.CharField("Veiksmas", max_length=3, choices=EventType.choices)
    scanned_at = models.DateTimeField("Nuskaitymo laikas", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-scanned_at", "-pk")
        verbose_name = "Darbo laiko žymėjimas"
        verbose_name_plural = "Darbo laiko žymėjimai"

    def __str__(self):
        return f"{self.worker_name} – {self.get_event_type_display()}"


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
    kitchenforce_id = models.PositiveIntegerField(
        "KitchenForce ID",
        blank=True,
        null=True,
        unique=True,
        help_text="Šio įrašo identifikatorius KitchenForce sistemoje.",
    )
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


class Purchase(models.Model):
    class Category(models.TextChoices):
        MEAT = "meat", "Mėsa"
        VEGETABLES = "vegetables", "Daržovės"
        OTHER = "other", "Kita"

    class Store(models.TextChoices):
        LIDL = "lidl", "Lidl"
        NORFA = "norfa", "Norfa"
        MAXIMA = "maxima", "Maxima"
        IKI = "iki", "Iki"
        OTHER = "other", "Kitos prekybos vietos"

    class Unit(models.TextChoices):
        KG = "kg", "kg"
        PIECE = "vnt", "vnt."
        LITRE = "l", "l"

    purchase_date = models.DateField("Pirkimo data", db_index=True)
    store = models.CharField("Parduotuvė", max_length=10, choices=Store.choices)
    category = models.CharField("Kategorija", max_length=12, choices=Category.choices)
    name = models.CharField("Prekės pavadinimas", max_length=255)
    quantity = models.DecimalField("Kiekis", max_digits=12, decimal_places=3,
                                   blank=True, null=True,
                                   validators=[MinValueValidator(Decimal("0.001"))])
    unit = models.CharField("Matavimo vienetas", max_length=3, choices=Unit.choices, default=Unit.KG, blank=True)
    unit_price = models.DecimalField("Vieneto kaina (€)", max_digits=12, decimal_places=4,
                                     blank=True, null=True,
                                     validators=[MinValueValidator(Decimal("0"))])
    total = models.DecimalField("Sumokėta suma (€)", max_digits=12, decimal_places=2,
                                validators=[MinValueValidator(Decimal("0"))],
                                help_text="Galutinė prekės suma iš čekio, pritaikius nuolaidas.")
    payment_adjustment = models.DecimalField(
        "Mokėjimo korekcija (€)", max_digits=12, decimal_places=2, default=Decimal("0.00"),
        help_text="Čekio apvalinimas ar mokėjimas lojalumo pinigais. Įveskite tik prie vienos čekio prekės; priežastį nurodykite pastabose.")
    receipt_reference = models.CharField("Čekio numeris / žyma", max_length=120, blank=True)
    notes = models.TextField("Pastabos", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-purchase_date", "category", "name", "pk")
        verbose_name = "Prekių pirkimas"
        verbose_name_plural = "Prekių pirkimai"
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="purchase_quantity_positive"),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name="purchase_price_nonnegative"),
            models.CheckConstraint(condition=models.Q(total__gte=0), name="purchase_total_nonnegative"),
        ]

    def clean(self):
        super().clean()
        self.name = " ".join(self.name.split())
        if not self.name:
            raise ValidationError({"name": "Įveskite prekės pavadinimą."})
        if self.quantity is not None and not self.unit:
            raise ValidationError({"unit": "Nurodykite kiekio matavimo vienetą."})
        if self.total is not None and self.payment_adjustment is not None and self.total + self.payment_adjustment < 0:
            raise ValidationError({"payment_adjustment": "Sumokėta suma su korekcija negali būti neigiama."})

    def __str__(self):
        return f"{self.purchase_date} – {self.name} ({self.get_store_display()})"
