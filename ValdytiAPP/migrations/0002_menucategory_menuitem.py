from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("valdyti", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MenuCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True, verbose_name="Pavadinimas")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="Rikiavimo eilė")),
                ("is_active", models.BooleanField(default=True, verbose_name="Rodoma meniu")),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subcategories",
                        to="valdyti.menucategory",
                        verbose_name="Pagrindinė kategorija",
                    ),
                ),
            ],
            options={
                "verbose_name": "Meniu kategorija",
                "verbose_name_plural": "Meniu kategorijos",
                "ordering": ("parent__sort_order", "parent__name", "sort_order", "name"),
            },
        ),
        migrations.CreateModel(
            name="MenuItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160, verbose_name="Patiekalo pavadinimas")),
                ("description", models.TextField(blank=True, verbose_name="Aprašymas")),
                ("price", models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True, verbose_name="Pirma kaina (€)")),
                ("second_price", models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True, verbose_name="Antra kaina (€)")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="Rikiavimo eilė")),
                ("is_active", models.BooleanField(default=True, verbose_name="Rodomas meniu")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="items",
                        to="valdyti.menucategory",
                        verbose_name="Kategorija",
                    ),
                ),
            ],
            options={
                "verbose_name": "Meniu patiekalas",
                "verbose_name_plural": "Meniu patiekalai",
                "ordering": ("category__sort_order", "category__name", "sort_order", "name"),
            },
        ),
    ]
