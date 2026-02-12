"""Product DTOs for the Service Layer.

Framework-agnostic data transfer objects using Pydantic v2.
These are the contracts between the API layer (DRF Serializers)
and the Service layer.  DTOs are immutable (``frozen=True``).

- ``CreateProductDTO``: input for product creation.
- ``UpdateProductDTO``: input for partial product updates.
- ``ProductOutputDTO``: output with all product fields.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

if TYPE_CHECKING:
    from modules.products.models import Product


# ---------------------------------------------------------------------------
# Input DTOs
# ---------------------------------------------------------------------------


class CreateProductDTO(BaseModel):
    """Immutable DTO for product creation requests.

    Validates:
    - ``sku`` is a non-empty string.
    - ``price`` is a Decimal greater than zero (RN-PRO-003).
    - ``stock_quantity`` is non-negative (RN-PRO-004).
    """

    model_config = ConfigDict(frozen=True)

    sku: str
    name: str
    price: Decimal
    description: str = ""
    stock_quantity: int = 0

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Price must be greater than zero.")
        return v

    @field_validator("stock_quantity")
    @classmethod
    def stock_must_be_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Stock quantity cannot be negative.")
        return v

    @field_validator("sku")
    @classmethod
    def sku_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("SKU must not be empty.")
        return v.strip().upper()


class UpdateProductDTO(BaseModel):
    """Immutable DTO for product update requests.

    All fields are optional — only supplied fields will be updated.
    """

    model_config = ConfigDict(frozen=True)

    name: str | None = None
    price: Decimal | None = None
    description: str | None = None
    stock_quantity: int | None = None
    status: str | None = None

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("Price must be greater than zero.")
        return v

    @field_validator("stock_quantity")
    @classmethod
    def stock_must_be_non_negative(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("Stock quantity cannot be negative.")
        return v


# ---------------------------------------------------------------------------
# Output DTO
# ---------------------------------------------------------------------------


class ProductOutputDTO(BaseModel):
    """Immutable DTO for product API responses."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    sku: str
    name: str
    description: str
    price: Decimal
    stock_quantity: int
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, product: Product) -> ProductOutputDTO:
        """Build an output DTO from a Product model instance."""
        return cls(
            id=product.id,
            sku=product.sku,
            name=product.name,
            description=product.description,
            price=product.price,
            stock_quantity=product.stock_quantity,
            status=product.status,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )
