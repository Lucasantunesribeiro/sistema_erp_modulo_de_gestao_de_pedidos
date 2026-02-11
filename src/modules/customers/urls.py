"""Customer URL configuration."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from modules.customers.views import CustomerViewSet

router = DefaultRouter(trailing_slash=True)
router.register("customers", CustomerViewSet, basename="customer")

urlpatterns = router.urls
