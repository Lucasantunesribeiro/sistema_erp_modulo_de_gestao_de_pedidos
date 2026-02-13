"""Order, OrderItem, and OrderStatusHistory models.

Business rules implemented:
- RN-PED-001: Invalid status transitions rejected (enforced at service layer).
- RN-PED-002: Each status change generates a history record.
- RN-PED-003: History contains old/new status, timestamp, user, and notes.
- Idempotency via ``idempotency_key`` unique constraint.
- Order number auto-generated as human-readable identifier.
- Customer FK uses PROTECT to preserve financial history.
- OrderItem snapshots product price at creation time (``unit_price``).
- OrderItem subtotal is always ``quantity * unit_price`` (calculated on save).
- Soft delete via ``deleted_at`` (inherited from SoftDeleteModel).
"""

from __future__ import annotations

import secrets
from decimal import Decimal
from typing import Any

import structlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from modules.core.models import BaseModel, SoftDeleteModel
from modules.orders.constants import (
    ORDER_NUMBER_MAX_RETRIES,
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    OrderStatus,
)
from shared.domain.events import DomainEventMixin

logger = structlog.get_logger(__name__)


class Order(DomainEventMixin, SoftDeleteModel):
    """Order aggregate root.

    ``order_number`` is a human-readable identifier auto-generated on first
    save (format: ``ORD-YYYYMMDD-XXXXXX``).  The UUIDv7 ``id`` is used for
    all internal references and API lookups.

    ``idempotency_key`` is nullable: only orders created via the public API
    carry a client-provided key.  MySQL allows multiple NULLs in a UNIQUE
    column, so non-API orders will not collide.
    """

    order_number: models.CharField = models.CharField(
        max_length=20, unique=True, editable=False
    )
    customer: models.ForeignKey = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status: models.CharField = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
    )
    total_amount: models.DecimalField = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    notes: models.TextField = models.TextField(blank=True, default="")
    idempotency_key: models.CharField = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "orders"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="orders_status_idx"),
            models.Index(fields=["-created_at"], name="orders_created_idx"),
        ]

    # ------------------------------------------------------------------
    # State Machine helpers
    # ------------------------------------------------------------------

    @property
    def is_terminal(self) -> bool:
        """Return ``True`` if the order is in a terminal state."""
        return self.status in TERMINAL_STATES

    def can_transition_to(self, new_status: str) -> bool:
        """Check whether transitioning to *new_status* is valid."""
        allowed = VALID_TRANSITIONS.get(self.status, set())
        return new_status in allowed

    # ------------------------------------------------------------------
    # Order number generation
    # ------------------------------------------------------------------

    @staticmethod
    def generate_order_number() -> str:
        """Generate a human-readable order number: ``ORD-YYYYMMDD-XXXXXX``."""
        now = timezone.now()
        suffix = secrets.token_hex(3).upper()
        return f"ORD-{now:%Y%m%d}-{suffix}"

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.order_number:
            for attempt in range(ORDER_NUMBER_MAX_RETRIES):
                candidate = self.generate_order_number()
                if not Order.objects.filter(order_number=candidate).exists():
                    self.order_number = candidate
                    break
            else:
                raise RuntimeError(
                    f"Failed to generate unique order_number after "
                    f"{ORDER_NUMBER_MAX_RETRIES} attempts"
                )
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        return f"{self.order_number} ({self.status})"


class OrderItem(SoftDeleteModel):
    """Line item linking an Order to a Product.

    ``unit_price`` is a **snapshot** of the product price at the time of
    purchase — it never changes even if the product price is updated later.
    ``subtotal`` is always ``quantity * unit_price``, recalculated on every save.

    Inherits ``SoftDeleteModel`` for consistency with Order.  If the parent
    Order is hard-deleted, CASCADE removes items at the database level.
    """

    order: models.ForeignKey = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="items",
    )
    product: models.ForeignKey = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    quantity: models.PositiveIntegerField = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    unit_price: models.DecimalField = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    subtotal: models.DecimalField = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        editable=False,
    )

    class Meta:
        db_table = "order_items"
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gte=1),
                name="order_items_quantity_positive",
            ),
        ]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self) -> None:
        super().clean()
        if self.quantity is not None and self.quantity < 1:
            raise ValidationError({"quantity": "Quantity must be at least 1."})

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.unit_price:
            unit_price = getattr(self.product, "price", None)
            if unit_price is None:
                raise ValidationError({"unit_price": "Product price is required."})
            self.unit_price = unit_price
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        return f"{self.product} x{self.quantity} (${self.subtotal})"


class OrderStatusHistory(BaseModel):
    """Append-only audit trail for order status transitions.

    Each record captures a single status change with the responsible user
    and optional notes (e.g. cancellation reason).

    This model intentionally inherits ``BaseModel`` (not ``SoftDeleteModel``)
    because audit records are **immutable** — they must never be edited or
    soft-deleted.  ``user`` is nullable: ``None`` means the change was
    performed by the system (e.g. automatic cancellation).
    """

    order: models.ForeignKey = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    old_status: models.CharField = models.CharField(  # noqa: DJ01
        max_length=20,
        choices=OrderStatus.choices,
        null=True,
        blank=True,
    )
    new_status: models.CharField = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
    )
    user: models.ForeignKey = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    notes: models.TextField = models.TextField(blank=True, default="")

    class Meta:
        db_table = "order_status_history"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["order", "-created_at"],
                name="osh_order_created_idx",
            ),
        ]

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        return f"{self.order} : {self.old_status} -> {self.new_status}"
