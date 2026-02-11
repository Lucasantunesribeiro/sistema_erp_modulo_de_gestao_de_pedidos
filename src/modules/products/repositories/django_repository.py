"""Django ORM implementation of the Product repository.

Satisfies ``IProductRepository`` using Django's QuerySet API.
Error handling follows the Null Object pattern: methods return ``None``
instead of raising HTTP-level exceptions — the Service Layer decides
how to translate a missing entity into an API response.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

from django.core.exceptions import ValidationError
from django.db import transaction

from modules.products.models import Product
from modules.products.repositories.interfaces import IProductRepository

logger = structlog.get_logger(__name__)


class ProductDjangoRepository(IProductRepository):
    """Concrete Product repository backed by Django ORM."""

    def get_by_id(self, id: str) -> Optional[Product]:
        """Retrieve a product by primary key.

        Returns ``None`` for non-existent or invalid IDs.
        """
        try:
            return Product.objects.filter(id=id).first()
        except (ValueError, ValidationError):
            return None

    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[Product]:
        """List products with optional Django ORM look-ups.

        Examples of valid filters::

            {"status": "active"}
            {"name__icontains": "widget"}
        """
        queryset = Product.objects.all()
        if filters:
            queryset = queryset.filter(**filters)
        return list(queryset)

    @transaction.atomic
    def save(self, entity: Product) -> Product:
        """Persist (create or update) a product."""
        entity.save()
        logger.info(
            "product.saved",
            product_id=str(entity.id),
            sku=entity.sku,
        )
        return entity

    @transaction.atomic
    def delete(self, id: str) -> bool:
        """Soft-delete a product by ID.

        Returns ``True`` if the product was found and soft-deleted,
        ``False`` if no product exists with the given ID.
        """
        product = self.get_by_id(id)
        if not product:
            return False
        product.delete()
        logger.info("product.soft_deleted", product_id=str(id))
        return True

    def get_by_sku(self, sku: str) -> Optional[Product]:
        """Retrieve a product by SKU (case-insensitive via upper normalisation)."""
        return Product.objects.filter(sku=sku.strip().upper()).first()

    def check_stock(self, id: str, quantity: int) -> bool:
        """Check whether sufficient stock exists for the requested quantity."""
        product = self.get_by_id(id)
        if not product:
            return False
        return product.stock_quantity >= quantity
