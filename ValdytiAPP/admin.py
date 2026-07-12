from django.contrib import admin

from .models import Worker


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "job_title", "phone", "email")
    search_fields = ("first_name", "last_name", "job_title", "phone", "email")

