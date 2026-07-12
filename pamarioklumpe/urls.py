"""Routes served by pamarioklumpe.lt."""

from django.urls import path

from .views import coming_soon

urlpatterns = [path("", coming_soon, name="coming-soon")]

