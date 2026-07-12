from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Worker",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("first_name", models.CharField(max_length=80, verbose_name="Vardas")),
                ("last_name", models.CharField(max_length=80, verbose_name="Pavardė")),
                ("job_title", models.CharField(max_length=120, verbose_name="Pareigos")),
                ("phone", models.CharField(blank=True, max_length=30, verbose_name="Telefono numeris")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="El. paštas")),
                ("notes", models.TextField(blank=True, verbose_name="Pastabos")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Darbuotojas", "verbose_name_plural": "Darbuotojai", "ordering": ("last_name", "first_name")},
        )
    ]

