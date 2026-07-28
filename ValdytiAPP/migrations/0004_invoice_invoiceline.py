# Generated manually for the initial invoice-management feature.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("valdyti", "0003_load_current_menu"),
    ]

    operations = [
        migrations.CreateModel(
            name="Invoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_file", models.FileField(upload_to="invoices/%Y/%m/", verbose_name="Originalus PDF")),
                ("original_filename", models.CharField(max_length=255, verbose_name="Originalus failo pavadinimas")),
                ("file_hash", models.CharField(db_index=True, max_length=64, unique=True, verbose_name="PDF SHA-256 piršto atspaudas")),
                ("invoice_number", models.CharField(blank=True, max_length=100, verbose_name="Sąskaitos numeris")),
                ("invoice_date", models.DateField(blank=True, null=True, verbose_name="Sąskaitos data")),
                ("due_date", models.DateField(blank=True, null=True, verbose_name="Apmokėjimo terminas")),
                ("supplier_name", models.CharField(blank=True, max_length=255, verbose_name="Tiekėjas")),
                ("supplier_company_code", models.CharField(blank=True, max_length=80, verbose_name="Tiekėjo įmonės kodas")),
                ("supplier_vat_id", models.CharField(blank=True, max_length=80, verbose_name="Tiekėjo PVM kodas")),
                ("supplier_address", models.TextField(blank=True, verbose_name="Tiekėjo adresas")),
                ("buyer_name", models.CharField(blank=True, max_length=255, verbose_name="Pirkėjas")),
                ("buyer_company_code", models.CharField(blank=True, max_length=80, verbose_name="Pirkėjo įmonės kodas")),
                ("buyer_vat_id", models.CharField(blank=True, max_length=80, verbose_name="Pirkėjo PVM kodas")),
                ("buyer_address", models.TextField(blank=True, verbose_name="Pirkėjo adresas")),
                ("subtotal", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name="Suma be PVM")),
                ("vat_rate", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name="PVM tarifas (%)")),
                ("vat_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name="PVM suma")),
                ("total", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name="Bendra suma")),
                ("currency", models.CharField(default="EUR", max_length=3, verbose_name="Valiuta")),
                ("notes", models.TextField(blank=True, verbose_name="Pastabos")),
                ("raw_extraction", models.JSONField(blank=True, default=dict, verbose_name="Nuskaityti duomenys")),
                ("parser_model", models.CharField(blank=True, max_length=100, verbose_name="Nuskaitymo modelis")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="uploaded_invoices", to=settings.AUTH_USER_MODEL, verbose_name="Įkėlė")),
            ],
            options={
                "verbose_name": "Sąskaita",
                "verbose_name_plural": "Sąskaitos",
                "ordering": ("-invoice_date", "-created_at"),
            },
        ),
        migrations.CreateModel(
            name="InvoiceLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("line_number", models.PositiveIntegerField(default=0, verbose_name="Eilutės numeris")),
                ("product_code", models.CharField(blank=True, max_length=100, verbose_name="Prekės kodas")),
                ("name", models.CharField(max_length=500, verbose_name="Prekė ar paslauga")),
                ("unit", models.CharField(blank=True, max_length=30, verbose_name="Vienetas")),
                ("quantity", models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True, verbose_name="Kiekis")),
                ("unit_price", models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True, verbose_name="Vieneto kaina be PVM")),
                ("total", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name="Eilutės suma be PVM")),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="valdyti.invoice", verbose_name="Sąskaita")),
            ],
            options={
                "verbose_name": "Sąskaitos eilutė",
                "verbose_name_plural": "Sąskaitos eilutės",
                "ordering": ("line_number", "pk"),
            },
        ),
    ]
