"""Combined routes used only by the local development server."""

from django.urls import include, path

from .views import coming_soon

urlpatterns = [
    path("", coming_soon, name="coming-soon"),
    path("valdyti/", include("ValdytiAPP.urls")),
]

