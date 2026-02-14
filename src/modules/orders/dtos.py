"""Order DTOs for the Service Layer.

Framework-agnostic data transfer objects using Pydantic v2.
These are the contracts between the API layer (DRF Serializers)
and the Service layer.  DTOs are immutable (``frozen=True``).

- ``CreateOrderItemDTO``: input for a single order line item.
- ``CreateOrderDTO``: input for order creation (nested items).
- ``OrderItemOutputDTO``: output for a single line item.
- ``StatusHistoryDTO``: output for a status history record.
- ``OrderOutputDTO``: output with items and history.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

if TYPE_CHECKING:
    from modules.orders.models import Order, OrderStatusHistory


# ---------------------------------------------------------------------------
# Input DTOs
# ---------------------------------------------------------------------------


class CreateOrderItemDTO(BaseModel):
    """Immutable DTO for a single order item in a creation request.

    The frontend sends ``product_id`` and ``quantity``.
    ``unit_price`` is resolved by the Service Layer from the product catalog.
    """

    model_config = ConfigDict(frozen=True)

    product_id: UUID
    quantity: int

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Quantity must be at least 1.")
        return v


class CreateOrderDTO(BaseModel):
    """Immutable DTO for order creation requests.

    Validates:
    - ``items`` must contain at least one item.
    - Each item quantity must be positive.
    """

    model_config = ConfigDict(frozen=True)

    customer_id: UUID
    items: List[CreateOrderItemDTO]
    notes: Optional[str] = ""
    idempotency_key: Optional[str] = None

    @field_validator("items")
    @classmethod
    def items_must_not_be_empty(
        cls, v: List[CreateOrderItemDTO]
    ) -> List[CreateOrderItemDTO]:
        if not v:
            raise ValueError("Order must have at least one item.")
        return v

    @model_validator(mode="after")
    def no_duplicate_products(self):
        """Prevent duplicate product IDs in the same order."""
        product_ids = [item.product_id for item in self.items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Duplicate product IDs are not allowed in the same order.")
        return self


# ---------------------------------------------------------------------------
# Output DTOs
# ---------------------------------------------------------------------------


class OrderItemOutputDTO(BaseModel):
    """Immutable DTO for order item API responses."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    product_id: UUID
    product_name: str
    product_sku: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class StatusHistoryDTO(BaseModel):
    """Immutable DTO for order status history API responses."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    old_status: Optional[str]
    new_status: str
    notes: str
    created_at: datetime

    @classmethod
    def from_entity(cls, history: OrderStatusHistory) -> StatusHistoryDTO:
        return cls(
            id=history.id,
            old_status=history.old_status,
            new_status=history.new_status,
            notes=history.notes,
            created_at=history.created_at,
        )


class OrderOutputDTO(BaseModel):
    """Immutable DTO for order API responses."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    order_number: str
    customer_id: UUID
    status: str
    total_amount: Decimal
    notes: str
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemOutputDTO]
    history: List[StatusHistoryDTO]

    @classmethod
    def from_entity(cls, order: Order) -> OrderOutputDTO:
        """Build an output DTO from an Order model instance.

        Assumes ``items`` and ``status_history`` are prefetched.
        """
        items = [
            OrderItemOutputDTO(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product.name,  # type: ignore[attr-defined]
                product_sku=item.product.sku,  # type: ignore[attr-defined]
                quantity=item.quantity,
                unit_price=item.unit_price,
                subtotal=item.subtotal,
            )
            for item in order.items.all()
        ]
        history = [StatusHistoryDTO.from_entity(h) for h in order.status_history.all()]
        return cls(
            id=order.id,
            order_number=order.order_number,
            customer_id=order.customer_id,
            status=order.status,
            total_amount=order.total_amount,
            notes=order.notes,
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=items,
            history=history,
        )
