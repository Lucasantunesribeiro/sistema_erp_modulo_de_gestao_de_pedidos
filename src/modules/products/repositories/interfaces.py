"""Product repository interface.

Extends ``IRepository[Product]`` with look-ups required by
business rules RN-PRO-001 (unique SKU) and stock verification.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Optional

from modules.core.repositories.interfaces import IRepository

if TYPE_CHECKING:
    from modules.products.models import Product


class IProductRepository(IRepository["Product"]):
    """Repository contract for the Product aggregate."""

    @abstractmethod
    def get_by_sku(self, sku: str) -> Optional[Product]:
        """Retrieve a product by SKU."""

    @abstractmethod
    def check_stock(self, id: str, quantity: int) -> bool:
        """Check whether sufficient stock exists for the requested quantity."""
