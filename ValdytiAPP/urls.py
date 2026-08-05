"""Routes served by valdyti.pamarioklumpe.lt."""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(template_name="ValdytiAPP/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.dashboard, name="dashboard"),
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
