from django.contrib import admin

from .models import AttendanceEvent, Invoice, InvoiceLine, MenuCategory, MenuItem, Worker


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "job_title", "chip_uid", "phone", "email")
    search_fields = ("first_name", "last_name", "job_title", "chip_uid", "phone", "email")


@admin.register(AttendanceEvent)
class AttendanceEventAdmin(admin.ModelAdmin):
    list_display = ("scanned_at", "worker_name", "event_type", "chip_uid")
    list_filter = ("event_type", "scanned_at")
    search_fields = ("worker_name", "chip_uid")
    readonly_fields = ("worker", "worker_name", "chip_uid", "event_type", "scanned_at")

    def has_add_permission(self, request):
        return False


@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "second_price", "sort_order", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name", "description")


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "supplier_name", "invoice_date", "total", "currency", "created_at")
    list_filter = ("currency", "invoice_date")
    search_fields = ("invoice_number", "supplier_name", "supplier_vat_id", "buyer_name")
    readonly_fields = ("file_hash", "original_filename", "raw_extraction", "parser_model", "created_at", "updated_at")
    inlines = (InvoiceLineInline,)
