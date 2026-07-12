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
]
