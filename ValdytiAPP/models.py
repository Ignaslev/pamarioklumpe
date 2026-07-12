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

