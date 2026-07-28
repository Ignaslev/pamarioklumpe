from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Q
from django.forms import inlineformset_factory
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView
from itertools import groupby

from .forms import InvoiceForm, InvoiceLineForm, InvoiceUploadForm, MenuCategoryForm, MenuItemForm, WorkerForm
from .invoice_parser import InvoiceParserError, cleaned_invoice_data, parse_invoice_pdf
from .models import Invoice, InvoiceLine, MenuCategory, MenuItem, Worker


InvoiceLineFormSet = inlineformset_factory(
    Invoice,
    InvoiceLine,
    form=InvoiceLineForm,
    extra=1,
    can_delete=True,
)


@login_required
def dashboard(request):
    return render(request, "ValdytiAPP/dashboard.html")


class WorkerListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Worker
    permission_required = "valdyti.view_worker"
    template_name = "ValdytiAPP/darbuotojai/worker_list.html"
    context_object_name = "workers"

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(job_title__icontains=query)
            )
        return queryset


class WorkerCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Worker
    form_class = WorkerForm
    permission_required = "valdyti.add_worker"
    template_name = "ValdytiAPP/darbuotojai/worker_form.html"
    success_url = reverse_lazy("worker-list")

    def form_valid(self, form):
        messages.success(self.request, "Darbuotojas pridėtas.")
        return super().form_valid(form)


class WorkerUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Worker
    form_class = WorkerForm
    permission_required = "valdyti.change_worker"
    template_name = "ValdytiAPP/darbuotojai/worker_form.html"
    success_url = reverse_lazy("worker-list")

    def form_valid(self, form):
        messages.success(self.request, "Darbuotojo informacija atnaujinta.")
        return super().form_valid(form)


class WorkerDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Worker
    permission_required = "valdyti.delete_worker"
    template_name = "ValdytiAPP/darbuotojai/worker_confirm_delete.html"
    success_url = reverse_lazy("worker-list")

    def form_valid(self, form):
        messages.success(self.request, "Darbuotojas ištrintas.")
        return super().form_valid(form)


class MenuListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = MenuItem
    permission_required = "valdyti.view_menuitem"
    template_name = "ValdytiAPP/meniu/menu_list.html"
    context_object_name = "menu_items"

    def get_queryset(self):
        queryset = MenuItem.objects.select_related("category", "category__parent")
        category_id = self.request.GET.get("category", "").strip()
        query = self.request.GET.get("q", "").strip()
        if category_id.isdigit():
            queryset = queryset.filter(category_id=category_id)
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(description__icontains=query))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        menu_items = list(context["menu_items"])
        context["menu_items"] = menu_items
        menu_groups = []
        for _, grouped_items in groupby(menu_items, key=lambda item: item.category_id):
            items = list(grouped_items)
            menu_groups.append((items[0].category, items))
        context["menu_groups"] = menu_groups
        context["categories"] = MenuCategory.objects.select_related("parent").all()
        return context


class MenuItemCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = MenuItem
    form_class = MenuItemForm
    permission_required = "valdyti.add_menuitem"
    template_name = "ValdytiAPP/meniu/menu_item_form.html"
    success_url = reverse_lazy("menu-list")

    def form_valid(self, form):
        messages.success(self.request, "Patiekalas pridėtas.")
        return super().form_valid(form)


class MenuItemUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = MenuItem
    form_class = MenuItemForm
    permission_required = "valdyti.change_menuitem"
    template_name = "ValdytiAPP/meniu/menu_item_form.html"
    success_url = reverse_lazy("menu-list")

    def form_valid(self, form):
        messages.success(self.request, "Patiekalo informacija atnaujinta.")
        return super().form_valid(form)


class MenuItemDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = MenuItem
    permission_required = "valdyti.delete_menuitem"
    template_name = "ValdytiAPP/meniu/menu_item_confirm_delete.html"
    success_url = reverse_lazy("menu-list")

    def form_valid(self, form):
        messages.success(self.request, "Patiekalas ištrintas.")
        return super().form_valid(form)


class MenuCategoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = MenuCategory
    permission_required = "valdyti.view_menucategory"
    template_name = "ValdytiAPP/meniu/category_list.html"
    context_object_name = "categories"

    def get_queryset(self):
        return MenuCategory.objects.select_related("parent").prefetch_related("items")


class MenuCategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = MenuCategory
    form_class = MenuCategoryForm
    permission_required = "valdyti.add_menucategory"
    template_name = "ValdytiAPP/meniu/category_form.html"
    success_url = reverse_lazy("menu-category-list")

    def form_valid(self, form):
        messages.success(self.request, "Meniu kategorija pridėta.")
        return super().form_valid(form)


class MenuCategoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = MenuCategory
    form_class = MenuCategoryForm
    permission_required = "valdyti.change_menucategory"
    template_name = "ValdytiAPP/meniu/category_form.html"
    success_url = reverse_lazy("menu-category-list")

    def form_valid(self, form):
        messages.success(self.request, "Meniu kategorija atnaujinta.")
        return super().form_valid(form)


class MenuCategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = MenuCategory
    permission_required = "valdyti.delete_menucategory"
    template_name = "ValdytiAPP/meniu/category_confirm_delete.html"
    success_url = reverse_lazy("menu-category-list")

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "Kategorijos ištrinti negalima, kol ji turi patiekalų arba subkategorijų.",
            )
            return redirect("menu-category-list")
        messages.success(self.request, "Meniu kategorija ištrinta.")
        return response


def normalized_text(value):
    return "".join(character for character in (value or "").casefold() if character.isalnum())


def find_business_duplicate(invoice_data):
    """Catch the same invoice saved in a re-exported PDF with a different hash."""
    invoice_number = invoice_data["invoice_number"]
    if not invoice_number:
        return None

    candidates = Invoice.objects.filter(invoice_number__iexact=invoice_number)
    supplier_vat_id = normalized_text(invoice_data["supplier_vat_id"])
    supplier_name = normalized_text(invoice_data["supplier_name"])
    for existing in candidates:
        if supplier_vat_id and normalized_text(existing.supplier_vat_id) == supplier_vat_id:
            return existing
        if not supplier_vat_id and supplier_name and normalized_text(existing.supplier_name) == supplier_name:
            return existing
    return None


class InvoiceListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Invoice
    permission_required = "valdyti.view_invoice"
    template_name = "ValdytiAPP/saskaitos/invoice_list.html"
    context_object_name = "invoices"

    def get_queryset(self):
        queryset = Invoice.objects.prefetch_related("lines")
        query = self.request.GET.get("q", "").strip()
        date_from = self.request.GET.get("date_from", "").strip()
        date_to = self.request.GET.get("date_to", "").strip()
        if query:
            queryset = queryset.filter(
                Q(invoice_number__icontains=query)
                | Q(supplier_name__icontains=query)
                | Q(supplier_vat_id__icontains=query)
                | Q(buyer_name__icontains=query)
            )
        if date_from:
            queryset = queryset.filter(invoice_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(invoice_date__lte=date_to)
        return queryset


class InvoiceUploadView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "valdyti.add_invoice"
    template_name = "ValdytiAPP/saskaitos/invoice_upload.html"

    def get_form(self, data=None, files=None):
        from django.conf import settings

        return InvoiceUploadForm(data=data, files=files, max_bytes=settings.INVOICE_UPLOAD_MAX_BYTES)

    def get(self, request):
        return render(request, self.template_name, {"form": self.get_form()})

    def post(self, request):
        form = self.get_form(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        uploaded_file = form.cleaned_data["pdf"]
        pdf_bytes = uploaded_file.read()
        file_hash = __import__("hashlib").sha256(pdf_bytes).hexdigest()
        existing_by_file = Invoice.objects.filter(file_hash=file_hash).first()
        if existing_by_file:
            messages.error(request, f"Šis PDF jau įkeltas kaip sąskaita „{existing_by_file}“. Antras įrašas nebuvo sukurtas.")
            return redirect("invoice-list")

        try:
            extracted_data, parser_model = parse_invoice_pdf(pdf_bytes, uploaded_file.name)
            invoice_data, lines = cleaned_invoice_data(extracted_data)
        except InvoiceParserError as exc:
            messages.error(request, str(exc))
            return render(request, self.template_name, {"form": form})

        existing_by_business_data = find_business_duplicate(invoice_data)
        if existing_by_business_data:
            messages.error(
                request,
                f"Galimas dublikatas: tiekėjo sąskaita „{existing_by_business_data}“ jau saugoma sistemoje. Naujas įrašas nebuvo sukurtas.",
            )
            return redirect("invoice-list")

        invoice = Invoice(
            **invoice_data,
            original_filename=uploaded_file.name[:255],
            file_hash=file_hash,
            raw_extraction=extracted_data,
            parser_model=parser_model,
            created_by=request.user,
        )
        try:
            with transaction.atomic():
                invoice.source_file.save(uploaded_file.name, ContentFile(pdf_bytes), save=False)
                invoice.save()
                InvoiceLine.objects.bulk_create([InvoiceLine(invoice=invoice, **line) for line in lines])
        except Exception:
            if invoice.source_file.name:
                invoice.source_file.delete(save=False)
            raise

        messages.success(request, "Sąskaita nuskaityta ir išsaugota. Prieš naudojant duomenis patikrinkite ją redagavimo lange.")
        return redirect("invoice-update", pk=invoice.pk)


class InvoiceUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "valdyti.change_invoice"
    template_name = "ValdytiAPP/saskaitos/invoice_form.html"

    def get_object(self):
        return get_object_or_404(Invoice.objects.prefetch_related("lines"), pk=self.kwargs["pk"])

    def get(self, request, *args, **kwargs):
        invoice = self.get_object()
        return render(request, self.template_name, {"invoice": invoice, "form": InvoiceForm(instance=invoice), "formset": InvoiceLineFormSet(instance=invoice)})

    def post(self, request, *args, **kwargs):
        invoice = self.get_object()
        form = InvoiceForm(request.POST, instance=invoice)
        formset = InvoiceLineFormSet(request.POST, instance=invoice)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
            messages.success(request, "Sąskaitos informacija atnaujinta.")
            return redirect("invoice-list")
        return render(request, self.template_name, {"invoice": invoice, "form": form, "formset": formset})


class InvoiceDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Invoice
    permission_required = "valdyti.delete_invoice"
    template_name = "ValdytiAPP/saskaitos/invoice_confirm_delete.html"
    success_url = reverse_lazy("invoice-list")

    def form_valid(self, form):
        source_file = self.get_object().source_file
        response = super().form_valid(form)
        if source_file:
            source_file.delete(save=False)
        messages.success(self.request, "Sąskaita ir jos originalus PDF ištrinti.")
        return response


class InvoicePdfView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "valdyti.view_invoice"

    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        if not invoice.source_file:
            raise Http404("Originalus PDF nerastas.")
        return FileResponse(
            invoice.source_file.open("rb"),
            content_type="application/pdf",
            as_attachment=request.GET.get("download") == "1",
            filename=invoice.original_filename,
        )
