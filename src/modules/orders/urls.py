"""Order URL configuration."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from modules.orders.views import OrderViewSet

router = DefaultRouter(trailing_slash=True)
router.register("orders", OrderViewSet, basename="order")

urlpatterns = router.urls
