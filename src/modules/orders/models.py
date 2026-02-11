"""Order model with status state machine and idempotency support.

Business rules implemented:
- RN-PED-001: Invalid status transitions rejected (enforced at service layer).
- Idempotency via ``idempotency_key`` unique constraint.
- Order number auto-generated as human-readable identifier.
- Customer FK uses PROTECT to preserve financial history.
- Soft delete via ``deleted_at`` (inherited from SoftDeleteModel).
"""

from __future__ import annotations

import secrets
from decimal import Decimal

import structlog

from django.db import models
from django.utils import timezone

from modules.core.models import SoftDeleteModel
from modules.orders.constants import ORDER_NUMBER_MAX_RETRIES, OrderStatus

logger = structlog.get_logger(__name__)


class Order(SoftDeleteModel):
    """Order aggregate root.

    ``order_number`` is a human-readable identifier auto-generated on first
    save (format: ``ORD-YYYYMMDD-XXXXXX``).  The UUIDv7 ``id`` is used for
    all internal references and API lookups.

    ``idempotency_key`` is nullable: only orders created via the public API
    carry a client-provided key.  MySQL allows multiple NULLs in a UNIQUE
    column, so non-API orders will not collide.
    """

    order_number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    notes = models.TextField(blank=True, default="")
    idempotency_key = models.CharField(
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

    def save(self, *args, **kwargs) -> None:
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
