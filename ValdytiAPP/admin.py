from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import AttendanceEvent, Invoice, InvoiceLine, MenuCategory, MenuItem, Purchase, PurchaseReceipt, Worker


@admin.register(PurchaseReceipt)
class PurchaseReceiptAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "purchase_date", "store", "status", "paid_total")
    list_filter = ("status", "store", "purchase_date")
    search_fields = ("receipt_number", "store_name", "original_filename")
    exclude = ("source_file",)

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields if field.name != "source_file") + ("receipt_link",)

    @admin.display(description="Čekio peržiūra ir redagavimas")
    def receipt_link(self, obj):
        return format_html('<a href="{}">Atidaryti čekį</a>', reverse("receipt-review", args=[obj.pk]))

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("purchase_date", "store", "category", "name", "quantity", "unit", "unit_price", "total")
    list_filter = ("store", "category", "purchase_date")
    search_fields = ("name", "receipt_reference", "notes")


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
