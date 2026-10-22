"""Routes served by valdyti.pamarioklumpe.lt."""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .purchase_views import PurchaseCreateView, PurchaseDailyPdfView, PurchaseDeleteView, PurchaseListView, PurchaseUpdateView
from .receipt_views import (ReceiptCancelView, ReceiptDeleteView, ReceiptOriginalView, ReceiptProcessView,
                            ReceiptReviewView, ReceiptStatusView, ReceiptUploadView, ReceiptMultipartCreateView,
                            ReceiptPartUploadView)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(template_name="ValdytiAPP/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("prekiu-pirkimas/", PurchaseListView.as_view(), name="purchase-list"),
    path("prekiu-pirkimas/cekiai/", ReceiptUploadView.as_view(), name="receipt-upload"),
    path("prekiu-pirkimas/cekiai/is-daliu/", ReceiptMultipartCreateView.as_view(), name="receipt-multipart-create"),
    path("prekiu-pirkimas/cekiai/<int:pk>/dalys/<int:position>/", ReceiptPartUploadView.as_view(), name="receipt-part-upload"),
    path("prekiu-pirkimas/cekiai/<int:pk>/nuskaityti/", ReceiptProcessView.as_view(), name="receipt-process"),
    path("prekiu-pirkimas/cekiai/<int:pk>/busena/", ReceiptStatusView.as_view(), name="receipt-status"),
    path("prekiu-pirkimas/cekiai/<int:pk>/atsaukti/", ReceiptCancelView.as_view(), name="receipt-cancel"),
    path("prekiu-pirkimas/cekiai/<int:pk>/", ReceiptReviewView.as_view(), name="receipt-review"),
    path("prekiu-pirkimas/cekiai/<int:pk>/originalas/", ReceiptOriginalView.as_view(), name="receipt-original"),
    path("prekiu-pirkimas/cekiai/<int:pk>/istrinti/", ReceiptDeleteView.as_view(), name="receipt-delete"),
    path("prekiu-pirkimas/pdf/", PurchaseDailyPdfView.as_view(), name="purchase-daily-pdf"),
    path("prekiu-pirkimas/naujas/", PurchaseCreateView.as_view(), name="purchase-create"),
    path("prekiu-pirkimas/<int:pk>/redaguoti/", PurchaseUpdateView.as_view(), name="purchase-update"),
    path("prekiu-pirkimas/<int:pk>/istrinti/", PurchaseDeleteView.as_view(), name="purchase-delete"),
    path("darbuotojai/", views.WorkerListView.as_view(), name="worker-list"),
    path("darbuotojai/naujas/", views.WorkerCreateView.as_view(), name="worker-create"),
    path("darbuotojai/<int:pk>/redaguoti/", views.WorkerUpdateView.as_view(), name="worker-update"),
    path("darbuotojai/<int:pk>/istrinti/", views.WorkerDeleteView.as_view(), name="worker-delete"),
    path("darbo-laikas/", views.AttendanceListView.as_view(), name="attendance-list"),
    path("darbo-laikas/suvestine/", views.AttendanceMonthlySummaryView.as_view(), name="attendance-monthly-summary"),
    path("api/clock/scan/", views.clock_scan_api, name="clock-scan-api"),
    path("meniu/", views.MenuListView.as_view(), name="menu-list"),
    path("meniu/naujas/", views.MenuItemCreateView.as_view(), name="menu-item-create"),
    path("meniu/<int:pk>/redaguoti/", views.MenuItemUpdateView.as_view(), name="menu-item-update"),
    path("meniu/<int:pk>/istrinti/", views.MenuItemDeleteView.as_view(), name="menu-item-delete"),
    path("meniu/kategorijos/", views.MenuCategoryListView.as_view(), name="menu-category-list"),
    path("meniu/kategorijos/nauja/", views.MenuCategoryCreateView.as_view(), name="menu-category-create"),
    path("meniu/kategorijos/<int:pk>/redaguoti/", views.MenuCategoryUpdateView.as_view(), name="menu-category-update"),
    path("meniu/kategorijos/<int:pk>/istrinti/", views.MenuCategoryDeleteView.as_view(), name="menu-category-delete"),
    path("saskaitos/", views.InvoiceListView.as_view(), name="invoice-list"),
    path("saskaitos/ikelti/", views.InvoiceUploadView.as_view(), name="invoice-upload"),
    path("saskaitos/<int:pk>/redaguoti/", views.InvoiceUpdateView.as_view(), name="invoice-update"),
    path("saskaitos/<int:pk>/istrinti/", views.InvoiceDeleteView.as_view(), name="invoice-delete"),
    path("saskaitos/<int:pk>/pdf/", views.InvoicePdfView.as_view(), name="invoice-pdf"),
]
