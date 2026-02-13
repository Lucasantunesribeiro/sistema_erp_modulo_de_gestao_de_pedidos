"""Product service layer (Use Cases).

Orchestrates business logic for the Product aggregate, delegating
persistence to the injected ``IProductRepository``.

Business rules enforced here:
- RN-PRO-001: SKU must be unique.
- RN-PRO-003: Price must be greater than zero (validated by DTO).
- RN-PRO-004: Stock cannot be negative (validated by DTO).
- RN-PRO-005: Soft delete via repository.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

import structlog
from django.db import transaction

from modules.products.exceptions import ProductAlreadyExists, ProductNotFound
from modules.products.models import Product

if TYPE_CHECKING:
    from modules.products.dtos import CreateProductDTO, UpdateProductDTO
    from modules.products.repositories.interfaces import IProductRepository

logger = structlog.get_logger(__name__)


class ProductService:
    """Application service for Product use-cases.

    Receives an ``IProductRepository`` via constructor injection (DIP).
    """

    def __init__(self, repository: IProductRepository) -> None:
        self._repo = repository

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @transaction.atomic
    def create_product(self, dto: CreateProductDTO) -> Product:
        """Create a new product after enforcing uniqueness rules.

        Raises:
            ProductAlreadyExists: if SKU is already taken (RN-PRO-001).
        """
        log = logger.bind(sku=dto.sku)

        if self._repo.get_by_sku(dto.sku):
            log.warning("product.duplicate_sku")
            raise ProductAlreadyExists(f"SKU '{dto.sku}' already registered.")

        product = Product(
            sku=dto.sku,
            name=dto.name,
            price=dto.price,
            description=dto.description,
            stock_quantity=dto.stock_quantity,
        )
        product = self._repo.save(product)
        log.info("product.created", product_id=str(product.id))
        return product

    @transaction.atomic
    def update_product(self, id: str, dto: UpdateProductDTO) -> Product:
        """Update an existing product with the supplied fields.

        Raises:
            ProductNotFound: if the product does not exist.
        """
        product = self._repo.get_by_id(id)
        if not product:
            raise ProductNotFound(f"Product {id} not found.")

        log = logger.bind(product_id=str(id))

        for field in ("name", "price", "description", "stock_quantity", "status"):
            value = getattr(dto, field)
            if value is not None:
                setattr(product, field, value)

        product = self._repo.save(product)
        log.info("product.updated")
        return product

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_products(self, filters: Optional[Dict[str, Any]] = None) -> List[Product]:
        """Return a list of products, optionally filtered."""
        return self._repo.list(filters)

    def get_product(self, id: str) -> Product:
        """Retrieve a single product by ID.

        Raises:
            ProductNotFound: if the product does not exist.
        """
        product = self._repo.get_by_id(id)
        if not product:
            raise ProductNotFound(f"Product {id} not found.")
        logger.info("product.retrieved", product_id=str(id))
        return product

    @transaction.atomic
    def delete_product(self, id: str) -> None:
        """Soft-delete a product (RN-PRO-005).

        Raises:
            ProductNotFound: if the product does not exist.
        """
        product = self._repo.get_by_id(id)
        if not product:
            raise ProductNotFound(f"Product {id} not found.")
        self._repo.delete(id)
        logger.info("product.soft_deleted", product_id=str(id))
