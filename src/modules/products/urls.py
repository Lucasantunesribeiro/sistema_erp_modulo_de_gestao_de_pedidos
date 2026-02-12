"""Product URL configuration."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from modules.products.views import ProductViewSet

router = DefaultRouter(trailing_slash=True)
router.register("products", ProductViewSet, basename="product")

urlpatterns = router.urls
